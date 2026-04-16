"""
Geração do Relatório Fiscal em PDF (ReportLab).

Estrutura ABRASF dos campos extraídos:
  InfNfse
  ├── ValorIssRetido       ← ISSQN retido (retenção real)
  ├── ValorLiquidoNfse     ← valor líquido da nota
  └── Servico
      └── Valores
          ├── ValorServicos    ← valor total da nota
          ├── ValorIr          ← IRRF retido
          ├── ValorPis         ← PIS retido
          ├── ValorCofins      ← COFINS retido
          ├── ValorInss        ← INSS retido
          ├── ValorCsll        ← CSLL retido
          └── OutrasRetencoes  ← outras retenções
"""
import io
import logging
from datetime import datetime
from pathlib import Path

from lxml import etree as lx

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer, Image, HRFlowable,
)

logger = logging.getLogger(__name__)

LOGO_PATH = (
    Path(__file__).parent.parent / "frontend" / "css" / "images" / "LOGO-ORIGINAL.png"
)
NS = "http://nfse.abrasf.org.br"

MESES_PT = [
    "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


# ─── Helpers XML ─────────────────────────────────────────────────────────────

def _find(el, tag):
    """Localiza um filho pelo nome, com e sem namespace ABRASF."""
    if el is None:
        return None
    result = el.find(tag)
    if result is not None:
        return result
    return el.find(f"{{{NS}}}{tag}")


def _txt(el, tag: str, default: str = "—") -> str:
    child = _find(el, tag)
    return child.text.strip() if child is not None and child.text else default


def _val(el, tag: str) -> float:
    """Extrai valor numérico de um filho; retorna 0.0 se ausente ou inválido."""
    raw = _txt(el, tag, "0")
    try:
        return float(raw)
    except (ValueError, TypeError):
        return 0.0


def _fmt_cnpj(cnpj: str) -> str:
    n = "".join(c for c in cnpj if c.isdigit())
    if len(n) == 14:
        return f"{n[:2]}.{n[2:5]}.{n[5:8]}/{n[8:12]}-{n[12:]}"
    return cnpj


def _brl(v: float) -> str:
    """Formata valor como moeda BRL sem prefixo (ex: 1.500,00)."""
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ─── Parser de notas ─────────────────────────────────────────────────────────

def _parse_notas(xml_str: str, tipo: str) -> list[dict]:
    """
    Extrai lista de notas ativas do XML retornado pelo WebService.
    Filtra automaticamente notas canceladas (Situacao=2 ou NfseCancelamento).

    Estrutura real do XML de produção (JP):
      InfNfse
      ├── PrestadorServico/RazaoSocial
      ├── DeclaracaoPrestacaoServico
      │   └── InfDeclaracaoPrestacaoServico
      │       ├── Competencia
      │       ├── Servico
      │       │   ├── IssRetido            (1=retido, 2=não)
      │       │   └── Valores
      │       │       ├── ValorServicos    ← valor bruto
      │       │       ├── ValorIss         ← ISS (retido quando IssRetido=1)
      │       │       ├── ValorIr          ← IRRF
      │       │       ├── ValorPis
      │       │       ├── ValorCofins
      │       │       ├── ValorInss
      │       │       ├── ValorCsll
      │       │       └── OutrasRetencoes
      │       └── Tomador/RazaoSocial
      └── ValoresNfse
          └── ValorLiquidoNfse             ← valor líquido
    """
    notas: list[dict] = []
    try:
        root = lx.fromstring(xml_str.encode("utf-8"))
    except Exception as e:
        logger.warning(f"[relatorio] Erro ao parsear XML: {e}")
        return notas

    comps = root.findall(".//CompNfse")
    if not comps:
        comps = root.findall(f".//{{{NS}}}CompNfse")

    for comp in comps:
        # ── Filtrar canceladas ──────────────────────────────────────────────
        if _find(comp, "NfseCancelamento") is not None:
            continue

        inf = comp.find(".//InfNfse")
        if inf is None:
            inf = comp.find(f".//{{{NS}}}InfNfse")
        if inf is None:
            continue
        if _txt(inf, "Situacao", "1") == "2":
            continue

        # ── InfDeclaracaoPrestacaoServico (caminho profundo) ────────────────
        inf_decl = inf.find(".//InfDeclaracaoPrestacaoServico")
        if inf_decl is None:
            inf_decl = inf.find(f".//{{{NS}}}InfDeclaracaoPrestacaoServico")

        # ── Servico e Valores ───────────────────────────────────────────────
        # Preferir dentro de inf_decl; fallback: busca global em inf
        servico = None
        if inf_decl is not None:
            servico = _find(inf_decl, "Servico")
        if servico is None:
            servico = inf.find(".//Servico")
        if servico is None:
            servico = inf.find(f".//{{{NS}}}Servico")

        valores = None
        if servico is not None:
            valores = _find(servico, "Valores")
        if valores is None:
            valores = inf.find(".//Valores")
        if valores is None:
            valores = inf.find(f".//{{{NS}}}Valores")

        # ── ValoresNfse (contém ValorLiquidoNfse) ───────────────────────────
        valores_nfse = _find(inf, "ValoresNfse")
        if valores_nfse is None:
            valores_nfse = inf.find(f".//{{{NS}}}ValoresNfse")

        # ── Prestador (direto em InfNfse) ───────────────────────────────────
        prest_el = _find(inf, "PrestadorServico")
        if prest_el is None:
            prest_el = inf.find(".//PrestadorServico")

        # ── Tomador (dentro de InfDeclaracaoPrestacaoServico) ───────────────
        tom_el = None
        if inf_decl is not None:
            tom_el = _find(inf_decl, "Tomador")
        if tom_el is None:
            # fallbacks para estruturas alternativas
            tom_el = _find(inf, "TomadorServico")
        if tom_el is None:
            tom_el = inf.find(".//Tomador")

        # ── Competência ─────────────────────────────────────────────────────
        comp_raw = ""
        if inf_decl is not None:
            comp_raw = _txt(inf_decl, "Competencia", "")
        if not comp_raw or comp_raw == "—":
            comp_raw = _txt(inf, "Competencia", "")
        if len(comp_raw) >= 7:
            comp_fmt = f"{comp_raw[5:7]}/{comp_raw[:4]}"
        else:
            comp_fmt = comp_raw or "—"

        # ── Data de emissão ─────────────────────────────────────────────────
        emissao_raw = _txt(inf, "DataEmissao", "")
        emissao = emissao_raw[:10].replace("-", "/") if emissao_raw else "—"

        # ── Valores monetários ──────────────────────────────────────────────
        valor_total = _val(valores, "ValorServicos")

        # ValorLiquidoNfse fica em ValoresNfse (não direto em InfNfse)
        valor_liquido = _val(valores_nfse, "ValorLiquidoNfse")
        if valor_liquido == 0.0:
            # fallback para estruturas que o colocam diretamente em InfNfse
            valor_liquido = _val(inf, "ValorLiquidoNfse")

        # ISSQN Retido: ValorIss quando IssRetido=1, senão 0
        iss_ret_flag = _txt(servico, "IssRetido", "2") if servico is not None else "2"
        issqn_retido = _val(valores, "ValorIss") if iss_ret_flag == "1" else 0.0
        # Fallback: tag ValorIssRetido explícita (algumas versões do WS)
        if issqn_retido == 0.0:
            issqn_retido = _val(inf, "ValorIssRetido")

        # Demais retenções — todas em Valores
        irrf   = _val(valores, "ValorIr")
        pis    = _val(valores, "ValorPis")
        cofins = _val(valores, "ValorCofins")
        inss   = _val(valores, "ValorInss")
        csll   = _val(valores, "ValorCsll")
        outras = _val(valores, "OutrasRetencoes")

        notas.append({
            "numero":        _txt(inf, "Numero"),
            "emissao":       emissao,
            "competencia":   comp_fmt,
            "tipo":          "Prestador" if tipo == "prestado" else "Tomador",
            "prestador":     _txt(prest_el, "RazaoSocial") if prest_el is not None else "—",
            "tomador":       _txt(tom_el,   "RazaoSocial") if tom_el   is not None else "—",
            "valor_total":   valor_total,
            "valor_liquido": valor_liquido,
            "issqn_retido":  issqn_retido,
            "irrf":          irrf,
            "pis":           pis,
            "cofins":        cofins,
            "inss":          inss,
            "csll":          csll,
            "outras":        outras,
        })

    return notas


# ─── Geração do PDF ──────────────────────────────────────────────────────────

def gerar_relatorio_pdf(
    xml_notas: str,
    tipo: str,
    competencia_mes: int,
    competencia_ano: int,
    razao_social: str,
    cnpj: str,
    inscricao_municipal: str,
) -> bytes:
    """Gera o PDF do Relatório Fiscal e devolve os bytes prontos para download."""

    notas = _parse_notas(xml_notas, tipo)
    periodo = f"{MESES_PT[competencia_mes]}/{competencia_ano}"
    hoje = datetime.now().strftime("%d/%m/%Y %H:%M")

    buf = io.BytesIO()
    PAGE_SIZE = landscape(A4)
    PAGE_W = PAGE_SIZE[0]
    H_MARGIN = 15 * mm

    doc = SimpleDocTemplate(
        buf,
        pagesize=PAGE_SIZE,
        leftMargin=H_MARGIN,
        rightMargin=H_MARGIN,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )

    # ── Estilos ───────────────────────────────────────────────────────────────
    s_title = ParagraphStyle("s_title", fontName="Helvetica-Bold", fontSize=11,
                             alignment=TA_CENTER, spaceAfter=1)
    s_sub   = ParagraphStyle("s_sub",   fontName="Helvetica", fontSize=8,
                             alignment=TA_CENTER,
                             textColor=colors.HexColor("#444444"), spaceAfter=2)
    s_emp   = ParagraphStyle("s_emp",   fontName="Helvetica", fontSize=8,
                             alignment=TA_CENTER, leading=12)
    s_foot  = ParagraphStyle("s_foot",  fontName="Helvetica", fontSize=7,
                             alignment=TA_CENTER,
                             textColor=colors.HexColor("#666666"))
    s_hdr   = ParagraphStyle("s_hdr",   fontName="Helvetica-Bold", fontSize=6,
                             alignment=TA_CENTER, leading=7.5,
                             textColor=colors.white)
    s_cl    = ParagraphStyle("s_cl",    fontName="Helvetica", fontSize=5.5,
                             alignment=TA_LEFT,   leading=7)
    s_cc    = ParagraphStyle("s_cc",    fontName="Helvetica", fontSize=5.5,
                             alignment=TA_CENTER, leading=7)
    s_cr    = ParagraphStyle("s_cr",    fontName="Helvetica", fontSize=5.5,
                             alignment=TA_RIGHT,  leading=7)
    s_tot   = ParagraphStyle("s_tot",   fontName="Helvetica-Bold", fontSize=6,
                             alignment=TA_RIGHT,  leading=7.5)
    s_totl  = ParagraphStyle("s_totl",  fontName="Helvetica-Bold", fontSize=6,
                             alignment=TA_LEFT,   leading=7.5)

    AZUL      = colors.HexColor("#1D4ED8")
    AZUL_LITE = colors.HexColor("#DBEAFE")
    CINZA     = colors.HexColor("#F0F6FF")
    BORDA     = colors.HexColor("#CBD5E1")

    story = []

    # ── Cabeçalho ─────────────────────────────────────────────────────────────
    if LOGO_PATH.exists():
        logo_img = Image(str(LOGO_PATH), width=44 * mm, height=16 * mm,
                         kind="proportional")
    else:
        logo_img = Paragraph(
            "<b>CONTATUS</b><br/>Assessoria Contábil",
            ParagraphStyle("lf", fontName="Helvetica-Bold", fontSize=9,
                           alignment=TA_LEFT),
        )

    tipo_label = "SERVIÇOS PRESTADOS" if tipo == "prestado" else "SERVIÇOS TOMADOS"
    title_cell = [
        Paragraph("RELATÓRIO FISCAL DE NOTAS DE SERVIÇO", s_title),
        Paragraph(f"{tipo_label} — Competência: <b>{periodo}</b>", s_sub),
        Paragraph(
            f"<b>{razao_social}</b><br/>"
            f"CNPJ: {_fmt_cnpj(cnpj)}&nbsp;&nbsp;&nbsp;"
            f"Insc. Municipal: {inscricao_municipal or '—'}"
            f"&nbsp;&nbsp;&nbsp;Emitido em: {hoje}",
            s_emp,
        ),
    ]

    header_tbl = Table([[logo_img, title_cell]], colWidths=[48 * mm, None])
    header_tbl.setStyle(TableStyle([
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",  (0, 0), (0,  0),  0),
        ("RIGHTPADDING", (1, 0), (1,  0),  0),
        ("LINEBELOW",    (0, 0), (-1, 0),  0.8, colors.HexColor("#94A3B8")),
    ]))
    story.append(header_tbl)
    story.append(Spacer(1, 4 * mm))

    # ── Tabela de notas ───────────────────────────────────────────────────────
    TW = PAGE_W - 2 * H_MARGIN  # largura útil da tabela

    # 15 colunas — proporções somam 1.0
    # Nº | Emissão | Tipo | Prestador | Tomador | Competência |
    # Vl.Total | Vl.Líquido | ISSQN Ret. | IRRF | PIS | COFINS | INSS | CSLL | Out.Ret.
    ratios = [
        0.044,  # Nº
        0.056,  # Emissão
        0.052,  # Tipo
        0.105,  # Prestador
        0.105,  # Tomador
        0.057,  # Competência
        0.069,  # Vl. Total
        0.069,  # Vl. Líquido
        0.065,  # ISSQN Ret.
        0.060,  # IRRF
        0.054,  # PIS
        0.060,  # COFINS
        0.054,  # INSS
        0.054,  # CSLL
        0.096,  # Out. Ret.
    ]
    col_widths = [TW * r for r in ratios]

    headers = [
        "Nº\nNFS-e", "Emissão", "Tipo",
        "Prestador", "Tomador", "Competência",
        "Vl. Total\n(R$)", "Vl. Líquido\n(R$)",
        "ISSQN\nRetido (R$)", "IRRF\n(R$)",
        "PIS\n(R$)", "COFINS\n(R$)", "INSS\n(R$)",
        "CSLL\n(R$)", "Out. Ret.\n(R$)",
    ]

    rows = [[Paragraph(h, s_hdr) for h in headers]]

    # Totalizadores
    tot_keys = ("valor_total", "valor_liquido", "issqn_retido",
                "irrf", "pis", "cofins", "inss", "csll", "outras")
    tot = {k: 0.0 for k in tot_keys}

    for n in notas:
        for k in tot_keys:
            tot[k] += n[k]

        rows.append([
            Paragraph(n["numero"],        s_cc),
            Paragraph(n["emissao"],       s_cc),
            Paragraph(n["tipo"],          s_cc),
            Paragraph(n["prestador"],     s_cl),
            Paragraph(n["tomador"],       s_cl),
            Paragraph(n["competencia"],   s_cc),
            Paragraph(_brl(n["valor_total"]),   s_cr),
            Paragraph(_brl(n["valor_liquido"]), s_cr),
            Paragraph(_brl(n["issqn_retido"]),  s_cr),
            Paragraph(_brl(n["irrf"]),           s_cr),
            Paragraph(_brl(n["pis"]),            s_cr),
            Paragraph(_brl(n["cofins"]),         s_cr),
            Paragraph(_brl(n["inss"]),           s_cr),
            Paragraph(_brl(n["csll"]),           s_cr),
            Paragraph(_brl(n["outras"]),         s_cr),
        ])

    # Linha de totais
    rows.append([
        Paragraph(f"TOTAL ({len(notas)} notas)", s_totl),
        Paragraph("", s_tot), Paragraph("", s_tot),
        Paragraph("", s_tot), Paragraph("", s_tot), Paragraph("", s_tot),
        Paragraph(_brl(tot["valor_total"]),   s_tot),
        Paragraph(_brl(tot["valor_liquido"]), s_tot),
        Paragraph(_brl(tot["issqn_retido"]),  s_tot),
        Paragraph(_brl(tot["irrf"]),           s_tot),
        Paragraph(_brl(tot["pis"]),            s_tot),
        Paragraph(_brl(tot["cofins"]),         s_tot),
        Paragraph(_brl(tot["inss"]),           s_tot),
        Paragraph(_brl(tot["csll"]),           s_tot),
        Paragraph(_brl(tot["outras"]),         s_tot),
    ])

    tbl = Table(rows, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        # Cabeçalho
        ("BACKGROUND",    (0, 0),  (-1, 0),  AZUL),
        ("FONTNAME",      (0, 0),  (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0),  (-1, 0),  6),
        ("ALIGN",         (0, 0),  (-1, 0),  "CENTER"),
        ("VALIGN",        (0, 0),  (-1, 0),  "MIDDLE"),
        # Dados — linhas alternadas
        ("ROWBACKGROUNDS",(0, 1),  (-1, -2), [colors.white, CINZA]),
        ("VALIGN",        (0, 1),  (-1, -1), "TOP"),
        # Grade
        ("GRID",          (0, 0),  (-1, -1), 0.3, BORDA),
        # Padding
        ("TOPPADDING",    (0, 0),  (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0),  (-1, -1), 2),
        ("LEFTPADDING",   (0, 0),  (-1, -1), 2),
        ("RIGHTPADDING",  (0, 0),  (-1, -1), 2),
        # Totais
        ("BACKGROUND",    (0, -1), (-1, -1), AZUL_LITE),
        ("FONTNAME",      (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE",     (0, -1), (-1, -1), 0.8, AZUL),
        ("SPAN",          (0, -1), (5,  -1)),
        ("ALIGN",         (0, -1), (5,  -1), "LEFT"),
        ("VALIGN",        (0, -1), (-1, -1), "MIDDLE"),
    ]))

    story.append(tbl)
    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5,
                            color=colors.HexColor("#94A3B8")))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        f"Relatório gerado em {hoje} pelo NFS-e JP Manager &nbsp;|&nbsp; "
        f"CONTATUS Assessoria Contábil &nbsp;|&nbsp; "
        f"{len(notas)} nota(s) ativa(s) — {periodo}",
        s_foot,
    ))

    doc.build(story)
    return buf.getvalue()
