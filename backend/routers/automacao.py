"""
Router de Automação: processa todas as empresas ativas para uma competência,
gera XMLs e relatórios PDF e devolve um arquivo .zip para download.

Estrutura do ZIP:
  Prestador/{codigo}/{MM-AAAA}/notas_prestador.xml
  Prestador/{codigo}/{MM-AAAA}/relatorio_prestador.pdf
  Tomador/{codigo}/{MM-AAAA}/notas_tomador.xml
  Tomador/{codigo}/{MM-AAAA}/relatorio_tomador.pdf
  Retroativo/{codigo}/{MM-AAAA}/retroativo_prestador.xml
  Retroativo/{codigo}/{MM-AAAA}/retroativo_tomado.xml
"""
import io
import logging
import zipfile
from typing import Optional

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from lxml import etree as lx

from database import get_db
from certificado import carregar_certificado
from models import Empresa
from schemas import (
    AutomacaoRequest,
    ConsultarServicoPrestadoRequest,
    ConsultaRetroativaRequest,
)
from xml_builder import (
    build_consultar_servico_prestado,
    build_consultar_servico_tomado,
    build_consultar_retroativo_prestado,
    build_consultar_retroativo_tomado,
)
from xml_signer import assinar_xml
from soap_client import chamar_webservice
from relatorio import gerar_relatorio_pdf

logger = logging.getLogger(__name__)
router = APIRouter()

NS = "http://nfse.abrasf.org.br"
MESES_PT = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
            "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]


# ─── Helpers internos ────────────────────────────────────────────────────────

def _label_competencia(mes: int, ano: int) -> str:
    return f"{mes:02d}-{ano}"


def _buscar_paginas(operacao: str, build_fn, dados, cnpj: str, cert) -> str:
    """
    Percorre todas as páginas de uma consulta de competência.
    Retorna XML combinado em <ListaNfse>.
    """
    todos: list[str] = []
    for pagina in range(1, 201):
        dados.pagina = pagina
        xml_str, ref_id = build_fn(dados, cnpj, getattr(dados, "inscricao_municipal", None))
        try:
            xml_assinado = assinar_xml(xml_str, cert.private_key, cert.certificate, ref_id)
            resultado = chamar_webservice(operacao, xml_assinado, cert)
        except Exception:
            break

        xml_resp = resultado.get("xml_resposta", "")
        try:
            root = lx.fromstring(xml_resp.encode("utf-8"))
            comps = root.findall(".//CompNfse") or root.findall(f".//{{{NS}}}CompNfse")
        except Exception:
            comps = []

        if comps:
            todos.extend(lx.tostring(c, encoding="unicode") for c in comps)

        if not resultado.get("sucesso") or not comps or len(comps) < 50:
            break

    lista = lx.Element("ListaNfse")
    for xml in todos:
        lista.append(lx.fromstring(xml))
    return lx.tostring(lista, encoding="unicode")


def _buscar_retroativo_prestado(mes: int, ano: int, cnpj: str, im: str, cert) -> str:
    """Consulta retroativa prestado com PeriodoEmissao."""
    todos: list[str] = []

    for pagina in range(1, 201):
        dados = ConsultaRetroativaRequest(
            competencia_mes=mes, competencia_ano=ano,
            pagina=pagina, inscricao_municipal=im,
            tipo="prestado", buscar_todas=True,
        )
        xml_str, ref_id = build_consultar_retroativo_prestado(dados, cnpj, im)
        try:
            xml_assinado = assinar_xml(xml_str, cert.private_key, cert.certificate, ref_id)
            resultado = chamar_webservice("ConsultarNfseServicoPrestado", xml_assinado, cert)
        except Exception:
            break

        xml_resp = resultado.get("xml_resposta", "")
        try:
            root = lx.fromstring(xml_resp.encode("utf-8"))
            comps = root.findall(".//CompNfse") or root.findall(f".//{{{NS}}}CompNfse")
        except Exception:
            comps = []

        if comps:
            todos.extend(lx.tostring(c, encoding="unicode") for c in comps)

        if not comps or len(comps) < 50:
            break

    lista = lx.Element("ListaNfse")
    for xml in todos:
        lista.append(lx.fromstring(xml))
    return lx.tostring(lista, encoding="unicode")


def _buscar_retroativo_tomado(mes: int, ano: int, cnpj: str, cert) -> str:
    """Consulta retroativa tomado: 6 competências anteriores com PeriodoCompetencia."""
    todos: list[str] = []

    for i in range(1, 7):
        mes_retro = mes - i
        ano_retro = ano
        while mes_retro <= 0:
            mes_retro += 12
            ano_retro -= 1

        dados = ConsultarServicoPrestadoRequest(
            competencia_mes=mes_retro, competencia_ano=ano_retro,
            pagina=1, tipo="tomado", buscar_todas=True,
        )
        for pagina in range(1, 201):
            dados.pagina = pagina
            xml_str, ref_id = build_consultar_servico_tomado(dados, cnpj, None)
            try:
                xml_assinado = assinar_xml(xml_str, cert.private_key, cert.certificate, ref_id)
                resultado = chamar_webservice("ConsultarNfseServicoTomado", xml_assinado, cert)
            except Exception:
                break

            if not resultado.get("sucesso"):
                break

            xml_resp = resultado.get("xml_resposta", "")
            try:
                root = lx.fromstring(xml_resp.encode("utf-8"))
                comps = root.findall(".//CompNfse") or root.findall(f".//{{{NS}}}CompNfse")
            except Exception:
                comps = []

            if comps:
                # Filtrar: emissão no mês selecionado e empresa NÃO é prestador
                for comp in comps:
                    prestador_cnpj = ""
                    for path in [".//PrestadorServico/IdentificacaoPrestador/CpfCnpj/Cnpj",
                                 ".//PrestadorServico/CpfCnpj/Cnpj"]:
                        el = comp.find(path)
                        if el is not None and el.text:
                            prestador_cnpj = el.text.strip().replace(".", "").replace("/", "").replace("-", "")
                            break
                    if prestador_cnpj == cnpj:
                        continue  # empresa é o prestador, não tomador

                    data_el = comp.find(".//DataEmissao")
                    if data_el is not None and data_el.text:
                        partes = data_el.text.strip()[:7]
                        if partes != f"{ano:04d}-{mes:02d}":
                            continue

                    todos.append(lx.tostring(comp, encoding="unicode"))

            if not resultado.get("sucesso") or not comps or len(comps) < 50:
                break

    lista = lx.Element("ListaNfse")
    for xml in todos:
        lista.append(lx.fromstring(xml))
    return lx.tostring(lista, encoding="unicode")


# ─── Endpoint principal ───────────────────────────────────────────────────────

@router.post("/executar")
def executar_automacao(
    dados: AutomacaoRequest,
    db: Session = Depends(get_db),
):
    """
    Processa todas as empresas selecionadas para a competência informada.
    Retorna um arquivo .zip com XMLs e relatórios PDF prontos para download.
    """
    mes = dados.competencia_mes
    ano = dados.competencia_ano
    label = _label_competencia(mes, ano)

    # Selecionar empresas
    query = db.query(Empresa)
    if dados.cnpjs:
        query = query.filter(Empresa.cnpj.in_(dados.cnpjs))
    else:
        query = query.filter(Empresa.ativo_automacao == True)
    empresas = query.order_by(Empresa.razao_social).all()

    if not empresas:
        raise HTTPException(status_code=400, detail="Nenhuma empresa ativa encontrada para processar.")

    erros: list[str] = []
    buf_zip = io.BytesIO()

    with zipfile.ZipFile(buf_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for emp in empresas:
            codigo = (emp.codigo or emp.cnpj).strip()
            im = emp.inscricao_municipal or ""

            try:
                cert = carregar_certificado(emp.cnpj, db)
            except Exception as e:
                erros.append(f"{emp.razao_social}: certificado — {e}")
                continue

            logger.info(f"[Automação] Processando {emp.razao_social} ({emp.cnpj}) — {label}")

            # ── 1. Prestado — notas da competência ─────────────────────────
            try:
                dados_prest = ConsultarServicoPrestadoRequest(
                    competencia_mes=mes, competencia_ano=ano,
                    pagina=1, inscricao_municipal=im,
                    tipo="prestado", buscar_todas=True,
                )
                xml_prestado = _buscar_paginas(
                    "ConsultarNfseServicoPrestado",
                    build_consultar_servico_prestado,
                    dados_prest, emp.cnpj, cert,
                )
                zf.writestr(
                    f"Prestador/{codigo}/{label}/notas_prestador.xml",
                    xml_prestado,
                )
                pdf_prest = gerar_relatorio_pdf(
                    xml_prestado, "prestado", mes, ano,
                    emp.razao_social, emp.cnpj, im,
                )
                zf.writestr(
                    f"Prestador/{codigo}/{label}/relatorio_prestador.pdf",
                    pdf_prest,
                )
            except Exception as e:
                erros.append(f"{emp.razao_social}: prestado — {e}")
                logger.exception(f"[Automação] Erro prestado {emp.cnpj}")

            # ── 2. Retroativo Prestado ──────────────────────────────────────
            try:
                xml_ret_prest = _buscar_retroativo_prestado(mes, ano, emp.cnpj, im, cert)
                zf.writestr(
                    f"Retroativo/{codigo}/{label}/retroativo_prestador.xml",
                    xml_ret_prest,
                )
            except Exception as e:
                erros.append(f"{emp.razao_social}: retroativo prestado — {e}")
                logger.exception(f"[Automação] Erro retroativo prestado {emp.cnpj}")

            # ── 3. Tomado — notas da competência ───────────────────────────
            try:
                dados_tom = ConsultarServicoPrestadoRequest(
                    competencia_mes=mes, competencia_ano=ano,
                    pagina=1, inscricao_municipal=im,
                    tipo="tomado", buscar_todas=True,
                )
                xml_tomado = _buscar_paginas(
                    "ConsultarNfseServicoTomado",
                    build_consultar_servico_tomado,
                    dados_tom, emp.cnpj, cert,
                )
                zf.writestr(
                    f"Tomador/{codigo}/{label}/notas_tomador.xml",
                    xml_tomado,
                )
                pdf_tom = gerar_relatorio_pdf(
                    xml_tomado, "tomado", mes, ano,
                    emp.razao_social, emp.cnpj, im,
                )
                zf.writestr(
                    f"Tomador/{codigo}/{label}/relatorio_tomador.pdf",
                    pdf_tom,
                )
            except Exception as e:
                erros.append(f"{emp.razao_social}: tomado — {e}")
                logger.exception(f"[Automação] Erro tomado {emp.cnpj}")

            # ── 4. Retroativo Tomado ────────────────────────────────────────
            try:
                xml_ret_tom = _buscar_retroativo_tomado(mes, ano, emp.cnpj, cert)
                zf.writestr(
                    f"Retroativo/{codigo}/{label}/retroativo_tomado.xml",
                    xml_ret_tom,
                )
            except Exception as e:
                erros.append(f"{emp.razao_social}: retroativo tomado — {e}")
                logger.exception(f"[Automação] Erro retroativo tomado {emp.cnpj}")

        # Incluir log de erros se houver
        if erros:
            zf.writestr("ERROS.txt", "\n".join(erros))

    buf_zip.seek(0)
    nome_zip = f"NFS-e_{label}_{len(empresas)}empresas.zip"

    return StreamingResponse(
        buf_zip,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{nome_zip}"'},
    )
