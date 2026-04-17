"""
Router NFS-e: implementa todos os 7 métodos do WebService GissOnline ABRASF 2.04.

Fluxo de cada endpoint:
1. Recebe dados do frontend (CNPJ via header X-Empresa-CNPJ)
2. Carrega certificado A1 correto do banco
3. Monta XML usando xml_builder
4. Assina digitalmente com xml_signer
5. Envia ao WebService via soap_client
6. Retorna resposta estruturada em JSON
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import logging
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import Optional
from lxml import etree as lx

from database import get_db
from certificado import carregar_certificado
from models import Empresa
from xml_builder import (
    build_lote_rps_sincrono, build_lote_rps_assincrono,
    build_consultar_lote, build_consultar_por_rps,
    build_consultar_faixa, build_cancelar_nfse, build_gerar_nfse,
    build_consultar_servico_prestado, build_consultar_servico_tomado,
    build_consultar_retroativo_prestado, build_consultar_retroativo_tomado,
)
from xml_signer import assinar_xml
from soap_client import chamar_webservice
from schemas import (
    LoteRpsRequest, ConsultarLoteRequest, ConsultarPorRpsRequest,
    ConsultarFaixaRequest, CancelarNfseRequest, GerarNfseRequest,
    ConsultarServicoPrestadoRequest, ConsultaRetroativaRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_cnpj_header(x_empresa_cnpj: Optional[str] = Header(None)) -> str:
    """Extrai e valida o CNPJ da empresa a partir do header X-Empresa-CNPJ."""
    if not x_empresa_cnpj:
        raise HTTPException(
            status_code=400,
            detail="Header 'X-Empresa-CNPJ' obrigatório. Selecione uma empresa no topo da interface."
        )
    cnpj = x_empresa_cnpj.strip().replace(".", "").replace("/", "").replace("-", "")
    if len(cnpj) != 14 or not cnpj.isdigit():
        raise HTTPException(status_code=400, detail="CNPJ inválido no header X-Empresa-CNPJ.")
    return cnpj


def _get_im(cnpj: str, db: Session, override: Optional[str] = None) -> str:
    """Retorna IM do request ou, se ausente, busca no cadastro da empresa."""
    if override and override.strip():
        return override.strip()
    empresa = db.query(Empresa).filter(Empresa.cnpj == cnpj).first()
    if not empresa or not empresa.inscricao_municipal:
        raise HTTPException(
            status_code=400,
            detail="Inscrição Municipal não informada e não cadastrada para esta empresa. Edite o cadastro da empresa."
        )
    return empresa.inscricao_municipal


def _executar_operacao(operacao: str, xml_str: str, ref_id: str, cnpj: str, db: Session) -> dict:
    """
    Pipeline comum: carrega certificado → assina XML → chama WebService.
    Centraliza o tratamento de erros para todos os endpoints.
    """
    # Carregar certificado da empresa
    try:
        cert = carregar_certificado(cnpj, db)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Assinar o XML
    try:
        xml_assinado = assinar_xml(xml_str, cert.private_key, cert.certificate, ref_id)
    except Exception as e:
        logger.error(f"Erro na assinatura XML: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao assinar o XML: {e}. Verifique se o certificado é RSA."
        )

    # Chamar WebService
    try:
        resultado = chamar_webservice(operacao, xml_assinado, cert)
    except Exception as e:
        logger.error(f"Erro no WebService ({operacao}): {e}")
        raise HTTPException(status_code=502, detail=str(e))

    return resultado


def _buscar_todas_paginas(
    operacao: str,
    build_fn,
    dados: "ConsultarServicoPrestadoRequest",
    cnpj: str,
    im,
    db: Session
) -> dict:
    """
    Percorre automaticamente todas as páginas do WebService (50 notas/página)
    e devolve um único XML com todas as CompNfse numa <ListaNfse> unificada.
    """
    try:
        cert = carregar_certificado(cnpj, db)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    todos_comps_xml: list[str] = []
    ultimo_resultado: dict = {}
    NS = "http://nfse.abrasf.org.br"
    MAX_PAGINAS = 200  # proteção contra loop infinito

    for pagina in range(1, MAX_PAGINAS + 1):
        dados.pagina = pagina

        xml_str, ref_id = build_fn(dados, cnpj, im)

        try:
            xml_assinado = assinar_xml(xml_str, cert.private_key, cert.certificate, ref_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erro ao assinar XML: {e}")

        try:
            resultado = chamar_webservice(operacao, xml_assinado, cert)
        except Exception as e:
            raise HTTPException(status_code=502, detail=str(e))

        ultimo_resultado = resultado

        # Primeira página com falha HTTP → retorna o erro direto
        if not resultado.get("sucesso"):
            if pagina == 1:
                return resultado
            break  # páginas anteriores OK, WS sinalizou fim (erro de negócio)

        xml_resp = resultado.get("xml_resposta", "")
        try:
            root = lx.fromstring(xml_resp.encode("utf-8"))
            # Localizar CompNfse com ou sem namespace
            comps = root.findall(".//CompNfse") or root.findall(f".//{{{NS}}}CompNfse")
            if not comps:
                break  # sem notas nesta página → chegamos ao fim
            # Serializar cada CompNfse para string antes de descartar a árvore
            todos_comps_xml.extend(lx.tostring(c, encoding="unicode") for c in comps)
            if len(comps) < 50:
                break  # última página (incompleta)
        except Exception:
            if pagina == 1:
                return resultado
            break

    # Montar XML combinado numa <ListaNfse> única
    lista_root = lx.Element("ListaNfse")
    for comp_xml in todos_comps_xml:
        lista_root.append(lx.fromstring(comp_xml))
    xml_combinado = lx.tostring(lista_root, encoding="unicode")

    logger.info(
        f"[{operacao}] {len(todos_comps_xml)} notas coletadas em {pagina} página(s)."
    )

    return {
        "sucesso": True,
        "xml_enviado": ultimo_resultado.get("xml_enviado", ""),
        "xml_resposta": xml_combinado,
        "status_code": 200,
        "erro": None,
    }


# ─── Helpers de filtragem retroativa ─────────────────────────────────────────

def _cnpj_de_paths(root, paths: list) -> str:
    """Tenta extrair um CNPJ (14 dígitos) percorrendo uma lista de XPaths lxml."""
    for path in paths:
        el = root.find(path)
        if el is not None and el.text:
            return el.text.strip().replace(".", "").replace("/", "").replace("-", "")
    return ""


def _e_cancelada(root, NS: str) -> bool:
    sit = root.find(".//Situacao") or root.find(f".//{{{NS}}}Situacao")
    if sit is not None and (sit.text or "").strip() == "2":
        return True
    return (
        root.find(".//NfseCancelamento") is not None
        or root.find(f".//{{{NS}}}NfseCancelamento") is not None
    )


def _filtrar_comps_retroativo(
    comps_xml: list,
    NS: str,
    cnpj_empresa: str,
    verificar_tomador: bool,
    emissao_mes: int,
    emissao_ano: int,
) -> list:
    """
    Filtra lista de CompNfse (strings XML) server-side:
      - Remove notas canceladas (Situacao=2 ou NfseCancelamento presente)
      - Se emissao_mes/ano informado: remove notas com DataEmissao fora desse mês
      - Se verificar_tomador=True: remove notas cujo TomadorServico CNPJ ≠ cnpj_empresa
    """
    resultado = []
    for comp_xml in comps_xml:
        try:
            root = lx.fromstring(comp_xml.encode("utf-8"))
        except Exception:
            resultado.append(comp_xml)
            continue

        if _e_cancelada(root, NS):
            continue

        if emissao_mes and emissao_ano:
            emissao_ok = True
            for path in [".//DataEmissao", f".//{{{NS}}}DataEmissao"]:
                el = root.find(path)
                if el is not None and el.text:
                    emissao_ok = el.text.strip()[:7] == f"{emissao_ano:04d}-{emissao_mes:02d}"
                    break
            if not emissao_ok:
                continue

        if verificar_tomador and cnpj_empresa:
            # Verificar pelo CNPJ do tomador (ABRASF padrão e variante JP)
            tomador_cnpj = _cnpj_de_paths(root, [
                ".//TomadorServico/IdentificacaoTomador/CpfCnpj/Cnpj",
                ".//TomadorServico/CpfCnpj/Cnpj",
                ".//Tomador/IdentificacaoTomador/CpfCnpj/Cnpj",
                ".//Tomador/CpfCnpj/Cnpj",
                f".//{{{NS}}}TomadorServico/{{{NS}}}IdentificacaoTomador/{{{NS}}}CpfCnpj/{{{NS}}}Cnpj",
                f".//{{{NS}}}Tomador/{{{NS}}}IdentificacaoTomador/{{{NS}}}CpfCnpj/{{{NS}}}Cnpj",
            ])
            if tomador_cnpj:
                if tomador_cnpj != cnpj_empresa:
                    continue  # CNPJ tomador não é a empresa consultada
            else:
                # Tomador usa CPF ou CNPJ não encontrado: se a empresa é o PRESTADOR,
                # esta nota foi emitida PELA empresa, não PARA ela → descartar
                prestador_cnpj = _cnpj_de_paths(root, [
                    ".//PrestadorServico/IdentificacaoPrestador/CpfCnpj/Cnpj",
                    ".//PrestadorServico/CpfCnpj/Cnpj",
                    f".//{{{NS}}}PrestadorServico/{{{NS}}}IdentificacaoPrestador/{{{NS}}}CpfCnpj/{{{NS}}}Cnpj",
                    f".//{{{NS}}}PrestadorServico/{{{NS}}}CpfCnpj/{{{NS}}}Cnpj",
                ])
                if prestador_cnpj and prestador_cnpj == cnpj_empresa:
                    continue  # Empresa é o PRESTADOR, não TOMADOR → descarta

        resultado.append(comp_xml)

    return resultado


# ─── 1. RecepcionarLoteRpsSincrono ────────────────────────────────────────────

@router.post("/lote-sincrono")
def recepcionar_lote_sincrono(
    dados: LoteRpsRequest,
    db: Session = Depends(get_db),
    cnpj: str = Depends(_get_cnpj_header)
):
    """
    Envia um lote de RPS e aguarda processamento síncrono.
    Retorna as NFS-e geradas ou os erros imediatamente.
    """
    im = _get_im(cnpj, db, dados.inscricao_municipal)
    dados.inscricao_municipal = im
    xml_str, ref_id = build_lote_rps_sincrono(dados, cnpj)
    return _executar_operacao("RecepcionarLoteRpsSincrono", xml_str, ref_id, cnpj, db)


# ─── 2. RecepcionarLoteRps (Assíncrono) ───────────────────────────────────────

@router.post("/lote-assincrono")
def recepcionar_lote_assincrono(
    dados: LoteRpsRequest,
    db: Session = Depends(get_db),
    cnpj: str = Depends(_get_cnpj_header)
):
    """
    Envia um lote de RPS para a fila de processamento.
    Retorna um protocolo para consulta posterior via /consultar-lote.
    """
    im = _get_im(cnpj, db, dados.inscricao_municipal)
    dados.inscricao_municipal = im
    xml_str, ref_id = build_lote_rps_assincrono(dados, cnpj)
    return _executar_operacao("RecepcionarLoteRps", xml_str, ref_id, cnpj, db)


# ─── 3. ConsultarLoteRps ──────────────────────────────────────────────────────

@router.post("/consultar-lote")
def consultar_lote(
    dados: ConsultarLoteRequest,
    db: Session = Depends(get_db),
    cnpj: str = Depends(_get_cnpj_header)
):
    """
    Consulta o status de um lote pelo número do protocolo.
    Use após RecepcionarLoteRps (assíncrono).
    """
    im = _get_im(cnpj, db, dados.inscricao_municipal)
    dados.inscricao_municipal = im
    xml_str, ref_id = build_consultar_lote(dados, cnpj)
    return _executar_operacao("ConsultarLoteRps", xml_str, ref_id, cnpj, db)


# ─── 4. ConsultarNfsePorRps ───────────────────────────────────────────────────

@router.post("/consultar-por-rps")
def consultar_por_rps(
    dados: ConsultarPorRpsRequest,
    db: Session = Depends(get_db),
    cnpj: str = Depends(_get_cnpj_header)
):
    """
    Busca uma NFS-e já emitida usando os dados do RPS (Número, Série, Tipo).
    """
    im = _get_im(cnpj, db, dados.inscricao_municipal)
    dados.inscricao_municipal = im
    xml_str, ref_id = build_consultar_por_rps(dados, cnpj)
    return _executar_operacao("ConsultarNfsePorRps", xml_str, ref_id, cnpj, db)


# ─── 5. ConsultarNfseFaixa ────────────────────────────────────────────────────

@router.post("/consultar-faixa")
def consultar_faixa(
    dados: ConsultarFaixaRequest,
    db: Session = Depends(get_db),
    cnpj: str = Depends(_get_cnpj_header)
):
    """
    Busca NFS-e dentro de uma faixa de numeração, com paginação.
    """
    im = _get_im(cnpj, db, dados.inscricao_municipal)
    dados.inscricao_municipal = im
    xml_str, ref_id = build_consultar_faixa(dados, cnpj)
    return _executar_operacao("ConsultarNfseFaixa", xml_str, ref_id, cnpj, db)


# ─── 6. CancelarNfse ──────────────────────────────────────────────────────────

@router.post("/cancelar")
def cancelar_nfse(
    dados: CancelarNfseRequest,
    db: Session = Depends(get_db),
    cnpj: str = Depends(_get_cnpj_header)
):
    """
    Solicita o cancelamento de uma NFS-e.
    Códigos de cancelamento: 1=Erro na emissão, 2=Serviço não prestado, 4=Emissão em duplicidade.
    """
    im = _get_im(cnpj, db, dados.inscricao_municipal)
    dados.inscricao_municipal = im
    xml_str, ref_id = build_cancelar_nfse(dados, cnpj)
    return _executar_operacao("CancelarNfse", xml_str, ref_id, cnpj, db)


# ─── 7. GerarNfse ─────────────────────────────────────────────────────────────

@router.post("/gerar")
def gerar_nfse(
    dados: GerarNfseRequest,
    db: Session = Depends(get_db),
    cnpj: str = Depends(_get_cnpj_header)
):
    """
    Geração direta de NFS-e (sem lote).
    Indicado para emissão unitária ou em baixo volume.
    """
    im = _get_im(cnpj, db, dados.inscricao_municipal)
    dados.inscricao_municipal = im
    xml_str, ref_id = build_gerar_nfse(dados, cnpj)
    return _executar_operacao("GerarNfse", xml_str, ref_id, cnpj, db)


# ─── 8. ConsultarNfseServicoPrestado (por competência) ────────────────────────

@router.post("/consultar-servico-prestado")
def consultar_servico_prestado(
    dados: ConsultarServicoPrestadoRequest,
    db: Session = Depends(get_db),
    cnpj: str = Depends(_get_cnpj_header)
):
    """
    Consulta NFS-e emitidas pelo prestador em uma competência (mês/ano).
    Usa ConsultarNfseServicoPrestado com filtro PeriodoCompetencia.
    """
    if dados.tipo == "tomado":
        # Tomador é identificado apenas por CNPJ — incluir IM filtraria
        # somente notas onde o emitente gravou também a IM do tomador,
        # excluindo a grande maioria emitida com CNPJ puro.
        if dados.buscar_todas:
            return _buscar_todas_paginas(
                "ConsultarNfseServicoTomado", build_consultar_servico_tomado,
                dados, cnpj, None, db
            )
        xml_str, ref_id = build_consultar_servico_tomado(dados, cnpj, None)
        return _executar_operacao("ConsultarNfseServicoTomado", xml_str, ref_id, cnpj, db)

    im = _get_im(cnpj, db, dados.inscricao_municipal)
    if dados.buscar_todas:
        return _buscar_todas_paginas(
            "ConsultarNfseServicoPrestado", build_consultar_servico_prestado,
            dados, cnpj, im, db
        )
    xml_str, ref_id = build_consultar_servico_prestado(dados, cnpj, im)
    return _executar_operacao("ConsultarNfseServicoPrestado", xml_str, ref_id, cnpj, db)


# ─── 9. ConsultaRetroativa (notas emitidas no mês selecionado com competência anterior) ──

def _buscar_retroativo_prestado(
    dados: ConsultaRetroativaRequest,
    cnpj: str,
    im: str,
    db: Session
) -> dict:
    """
    Prestado retroativo: filtra por PeriodoEmissao (mês selecionado).
    Extrai CompNfse mesmo quando o WS retorna HTTP não-200, pois alguns
    servidores sinalizam 'fim de registros' com status de erro mas ainda
    incluem notas no corpo da resposta.
    """
    try:
        cert = carregar_certificado(cnpj, db)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    todos_comps_xml: list[str] = []
    NS = "http://nfse.abrasf.org.br"
    ultimo_resultado: dict = {}

    for pagina in range(1, 201):
        dados.pagina = pagina
        xml_str, ref_id = build_consultar_retroativo_prestado(dados, cnpj, im)

        try:
            xml_assinado = assinar_xml(xml_str, cert.private_key, cert.certificate, ref_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erro ao assinar XML: {e}")

        try:
            resultado = chamar_webservice("ConsultarNfseServicoPrestado", xml_assinado, cert)
        except Exception as e:
            if pagina == 1:
                raise HTTPException(status_code=502, detail=str(e))
            break

        ultimo_resultado = resultado
        xml_resp = resultado.get("xml_resposta", "")

        try:
            root = lx.fromstring(xml_resp.encode("utf-8"))
            comps = root.findall(".//CompNfse") or root.findall(f".//{{{NS}}}CompNfse")
        except Exception:
            comps = []

        if comps:
            todos_comps_xml.extend(lx.tostring(c, encoding="unicode") for c in comps)

        # Parar se: erro do WS, sem notas, ou última página (< 50)
        if not resultado.get("sucesso") or not comps or len(comps) < 50:
            if not todos_comps_xml:
                # Nenhuma nota encontrada em nenhuma página — retorna erro real
                return resultado
            break

    # Remover canceladas server-side (frontend também filtra, mas aqui é mais limpo)
    todos_comps_xml = _filtrar_comps_retroativo(
        todos_comps_xml, NS, cnpj,
        verificar_tomador=False,
        emissao_mes=0, emissao_ano=0,
    )

    lista_root = lx.Element("ListaNfse")
    for comp_xml in todos_comps_xml:
        lista_root.append(lx.fromstring(comp_xml))
    xml_combinado = lx.tostring(lista_root, encoding="unicode")

    logger.info(f"[RetroativoPrestado] {len(todos_comps_xml)} nota(s) após filtro.")
    return {
        "sucesso": True,
        "xml_enviado": ultimo_resultado.get("xml_enviado", ""),
        "xml_resposta": xml_combinado,
        "status_code": 200,
        "erro": None,
    }


def _buscar_retroativo_tomado(
    dados: ConsultaRetroativaRequest,
    cnpj: str,
    db: Session
) -> dict:
    """
    Tomado retroativo: consulta cada uma das 6 competências anteriores com
    PeriodoCompetencia (método comprovado para tomado). O frontend filtra
    pela data de emissão que cai dentro do mês selecionado.
    """
    try:
        cert = carregar_certificado(cnpj, db)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    todos_comps_xml: list[str] = []
    NS = "http://nfse.abrasf.org.br"

    for i in range(1, 7):
        # Calcular o mês retroativo i
        mes_retro = dados.competencia_mes - i
        ano_retro = dados.competencia_ano
        while mes_retro <= 0:
            mes_retro += 12
            ano_retro -= 1

        # Reutilizar ConsultarServicoPrestadoRequest apenas como portador dos campos
        dados_mes = ConsultarServicoPrestadoRequest(
            competencia_mes=mes_retro,
            competencia_ano=ano_retro,
            pagina=1,
            tipo="tomado",
            buscar_todas=True,
        )

        for pagina in range(1, 201):
            dados_mes.pagina = pagina
            xml_str, ref_id = build_consultar_servico_tomado(dados_mes, cnpj, None)

            try:
                xml_assinado = assinar_xml(xml_str, cert.private_key, cert.certificate, ref_id)
            except Exception:
                break

            try:
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

            if not comps:
                break

            todos_comps_xml.extend(lx.tostring(c, encoding="unicode") for c in comps)
            if len(comps) < 50:
                break

    # Filtros server-side:
    #   1. Remove canceladas
    #   2. Emissão deve cair no mês/ano selecionado
    #   3. TomadorServico CNPJ deve ser da empresa consultada
    total_bruto = len(todos_comps_xml)
    todos_comps_xml = _filtrar_comps_retroativo(
        todos_comps_xml, NS, cnpj,
        verificar_tomador=True,
        emissao_mes=dados.competencia_mes,
        emissao_ano=dados.competencia_ano,
    )

    lista_root = lx.Element("ListaNfse")
    for comp_xml in todos_comps_xml:
        lista_root.append(lx.fromstring(comp_xml))
    xml_combinado = lx.tostring(lista_root, encoding="unicode")

    logger.info(
        f"[RetroativoTomado] {len(todos_comps_xml)} nota(s) após filtro "
        f"(de {total_bruto} coletada(s) em 6 competências)."
    )
    return {
        "sucesso": True,
        "xml_enviado": "",
        "xml_resposta": xml_combinado,
        "status_code": 200,
        "erro": None,
    }


@router.post("/consultar-retroativo")
def consultar_retroativo(
    dados: ConsultaRetroativaRequest,
    db: Session = Depends(get_db),
    cnpj: str = Depends(_get_cnpj_header)
):
    """
    Consulta NFS-e retroativas:
    - Prestado: filtra por PeriodoEmissao no mês selecionado; frontend filtra por competência.
    - Tomado: consulta as 6 competências anteriores com PeriodoCompetencia; frontend filtra por emissão.
    """
    if dados.tipo == "tomado":
        return _buscar_retroativo_tomado(dados, cnpj, db)

    im = _get_im(cnpj, db, dados.inscricao_municipal)
    return _buscar_retroativo_prestado(dados, im=im, cnpj=cnpj, db=db)


# ─── Utilitário: inspecionar WSDL ────────────────────────────────────────────

@router.get("/inspecionar-wsdl")
def inspecionar_wsdl(
    db: Session = Depends(get_db),
    cnpj: str = Depends(_get_cnpj_header)
):
    """
    Busca o WSDL do WebService usando o certificado da empresa ativa e
    retorna a lista real de operações disponíveis.

    Use este endpoint quando receber erros "operation was not recognized"
    para confirmar os nomes corretos das operações no WSDL do município.
    """
    import requests as req
    import os
    import tempfile
    from lxml import etree as lx

    try:
        cert = carregar_certificado(cnpj, db)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    ambiente = os.getenv("AMBIENTE", "homologacao").lower()
    base_url = (
        os.getenv("WSDL_PRODUCAO", "https://ws-joaopessoa.giss.com.br/service-ws/nf/nfse-ws")
        if ambiente == "producao"
        else os.getenv("WSDL_HOMOLOGACAO", "https://ws-homologacao-rtc.giss.com.br/service-ws/nf/nfse-ws")
    )
    wsdl_url = base_url + "?wsdl"

    # Criar arquivos PEM temporários
    cf = tempfile.NamedTemporaryFile(delete=False, suffix="_c.pem")
    cf.write(cert.cert_pem); cf.close()
    kf = tempfile.NamedTemporaryFile(delete=False, suffix="_k.pem")
    kf.write(cert.key_pem); kf.close()

    try:
        resp = req.get(wsdl_url, cert=(cf.name, kf.name), verify=False, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Não foi possível buscar o WSDL: {e}")
    finally:
        import os as _os
        _os.unlink(cf.name); _os.unlink(kf.name)

    try:
        root = lx.fromstring(resp.content)
        # Namespace WSDL
        wsdl_ns = "http://schemas.xmlsoap.org/wsdl/"
        ops = [el.get("name") for el in root.iter(f"{{{wsdl_ns}}}operation") if el.get("name")]
        ops = sorted(set(ops))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao parsear WSDL: {e}")

    from soap_client import OPERACOES_SOAP
    mapeamento_atual = {k: v for k, v in OPERACOES_SOAP.items()}

    return {
        "ambiente": ambiente,
        "wsdl_url": wsdl_url,
        "operacoes_no_wsdl": ops,
        "mapeamento_atual": mapeamento_atual,
        "nota": (
            "Se alguma operação do mapeamento_atual não aparecer em operacoes_no_wsdl, "
            "edite OPERACOES_SOAP em backend/soap_client.py com o nome correto."
        )
    }
