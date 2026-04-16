"""
Cliente SOAP para comunicação com os WebServices NFS-e de João Pessoa.

Existem DOIS serviços com protocolos diferentes:

══════════════════════════════════════════════════════════════════
HOMOLOGAÇÃO — GissOnline/Eicon (ABRASF 2.04)
  URL:  https://ws-homologacao-rtc.giss.com.br/service-ws/nf/nfse-ws
  WSDL: ?wsdl=nfse.wsdl
  Protocolo:
    - XML assinado enviado como string escapada em <nfseDadosMsg>
    - Cabeçalho em <nfseCabecMsg>
    - Elemento do body: <ns1:{Operacao}Request>
    - SOAPAction: http://nfse.abrasf.org.br/{Operacao}
    - Resposta em: <outputXML>
    - Operação faixa: ConsultarNfsePorFaixa

══════════════════════════════════════════════════════════════════
PRODUÇÃO — Receita João Pessoa (ABRASF v2.03)
  URL:  https://receita.joaopessoa.pb.gov.br/notafiscal-abrasfv203-ws/NotaFiscalSoap
  WSDL: ?wsdl (NotaFiscalSoap.xml)
  Protocolo:
    - XML assinado embutido DIRETAMENTE no corpo SOAP (não como string)
    - Sem nfseCabecMsg
    - Elemento do body: <tns:{Operacao}> contendo o XML de envio
    - SOAPAction: vazia ("")
    - Resposta em: <{Operacao}Resposta>
    - Operação faixa: ConsultarNfseFaixa
"""
import os
import tempfile
import logging
from xml.sax.saxutils import escape
from lxml import etree
import requests
from certificado import CertificadoCarregado

logger = logging.getLogger(__name__)

# Namespace comum aos dois serviços
WS_NAMESPACE = "http://nfse.abrasf.org.br"

# Cabeçalho ABRASF usado no modo homologação (nfseCabecMsg)
_CABECALHO_XML = (
    '<cabecalho xmlns="http://nfse.abrasf.org.br" versao="2.04">'
    '<versaoDados>2.04</versaoDados>'
    '</cabecalho>'
)

# ─── Mapeamento de operações: homologação (GissOnline) ───────────────────────
# O GissOnline renomeia algumas operações em relação ao padrão ABRASF.
OPERACOES_GISS = {
    "RecepcionarLoteRpsSincrono":    "RecepcionarLoteRpsSincrono",
    "RecepcionarLoteRps":            "RecepcionarLoteRps",
    "ConsultarLoteRps":              "ConsultarLoteRps",
    "ConsultarNfsePorRps":           "ConsultarNfsePorRps",
    "ConsultarNfseFaixa":            "ConsultarNfsePorFaixa",   # renomeado no GissOnline
    "CancelarNfse":                  "CancelarNfse",
    "GerarNfse":                     "GerarNfse",
    "SubstituirNfse":                "SubstituirNfse",
    "ConsultarNfseServicoPrestado":  "ConsultarNfseServicoPrestado",
    "ConsultarNfseServicoTomado":    "ConsultarNfseServicoTomado",
}

# ─── Mapeamento de operações: produção (Receita JP) ──────────────────────────
# No webservice da Prefeitura, os nomes batem exatamente com o padrão ABRASF.
OPERACOES_RECEITA = {
    "RecepcionarLoteRpsSincrono":    "RecepcionarLoteRpsSincrono",
    "RecepcionarLoteRps":            "RecepcionarLoteRps",
    "ConsultarLoteRps":              "ConsultarLoteRps",
    "ConsultarNfsePorRps":           "ConsultarNfsePorRps",
    "ConsultarNfseFaixa":            "ConsultarNfseFaixa",      # nome correto na Receita JP
    "CancelarNfse":                  "CancelarNfse",
    "GerarNfse":                     "GerarNfse",
    "SubstituirNfse":                "SubstituirNfse",
    "ConsultarNfseServicoPrestado":  "ConsultarNfseServicoPrestado",
    "ConsultarNfseServicoTomado":    "ConsultarNfseServicoTomado",
}

# Exportado para o endpoint /api/nfse/inspecionar-wsdl
OPERACOES_SOAP = OPERACOES_GISS  # retrocompatibilidade; o real depende do ambiente


def _get_ambiente() -> str:
    return os.getenv("AMBIENTE", "homologacao").lower()


def _get_service_url() -> str:
    if _get_ambiente() == "producao":
        return os.getenv(
            "WSDL_PRODUCAO",
            "https://receita.joaopessoa.pb.gov.br/notafiscal-abrasfv203-ws/NotaFiscalSoap"
        )
    return os.getenv(
        "WSDL_HOMOLOGACAO",
        "https://ws-homologacao-rtc.giss.com.br/service-ws/nf/nfse-ws"
    )


def _get_operacoes() -> dict:
    return OPERACOES_RECEITA if _get_ambiente() == "producao" else OPERACOES_GISS


# ─── Montagem do envelope ────────────────────────────────────────────────────

def _build_envelope_giss(operacao_wsdl: str, xml_payload: str) -> str:
    """
    Envelope para o GissOnline (homologação).
    O XML assinado é enviado como string escapada dentro de <nfseDadosMsg>.
    """
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<soapenv:Envelope'
        ' xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"'
        f' xmlns:ns1="{WS_NAMESPACE}">'
        '<soapenv:Header/>'
        '<soapenv:Body>'
        f'<ns1:{operacao_wsdl}Request>'
        f'<nfseCabecMsg>{escape(_CABECALHO_XML)}</nfseCabecMsg>'
        f'<nfseDadosMsg>{escape(xml_payload)}</nfseDadosMsg>'
        f'</ns1:{operacao_wsdl}Request>'
        '</soapenv:Body>'
        '</soapenv:Envelope>'
    )


def _build_envelope_receita(operacao_wsdl: str, xml_payload: str) -> str:
    """
    Envelope para a Receita JP (produção).
    O XML assinado é embutido DIRETAMENTE no corpo SOAP (não como string).
    Estrutura: <tns:Operacao><OperacaoEnvio>...xml assinado...</OperacaoEnvio></tns:Operacao>
    """
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<soapenv:Envelope'
        ' xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"'
        f' xmlns:tns="{WS_NAMESPACE}">'
        '<soapenv:Header/>'
        '<soapenv:Body>'
        f'<tns:{operacao_wsdl}>'
        f'{xml_payload}'
        f'</tns:{operacao_wsdl}>'
        '</soapenv:Body>'
        '</soapenv:Envelope>'
    )


def _build_soap_envelope(operacao_wsdl: str, xml_payload: str) -> tuple[str, str]:
    """
    Retorna (envelope_xml, soapaction) conforme o ambiente ativo.
    """
    if _get_ambiente() == "producao":
        envelope = _build_envelope_receita(operacao_wsdl, xml_payload)
        soapaction = '""'  # SOAPAction vazia conforme WSDL da Receita JP
    else:
        envelope = _build_envelope_giss(operacao_wsdl, xml_payload)
        soapaction = f'"{WS_NAMESPACE}/{operacao_wsdl}"'
    return envelope, soapaction


# ─── Parsing da resposta ─────────────────────────────────────────────────────

def _parse_soap_response(response_text: str, operacao_wsdl: str) -> str:
    """
    Extrai o conteúdo relevante da resposta SOAP conforme o ambiente.

    - Homologação (GissOnline): extrai <outputXML>
    - Produção (Receita JP):    extrai <{Operacao}Resposta> ou <{Operacao}Response>
    """
    try:
        root = etree.fromstring(response_text.encode("utf-8"))

        if _get_ambiente() == "producao":
            # Procurar elemento *Resposta (ex: ConsultarNfseFaixaResposta)
            resposta_tag = f"{operacao_wsdl}Resposta"
            result = root.find(f".//{resposta_tag}")
            if result is None:
                result = root.find(f".//{{{WS_NAMESPACE}}}{resposta_tag}")
            if result is not None:
                return etree.tostring(result, encoding="unicode")
        else:
            # GissOnline: campo outputXML
            result = root.find(".//outputXML")
            if result is None:
                result = root.find(f".//{{{WS_NAMESPACE}}}outputXML")
            if result is not None and result.text:
                return result.text.strip()

        # Fallback: retornar o body inteiro
        body = root.find(".//{http://schemas.xmlsoap.org/soap/envelope/}Body")
        if body is not None:
            return etree.tostring(body, encoding="unicode")

    except Exception as e:
        logger.warning(f"Não foi possível parsear resposta SOAP: {e}")

    return response_text


# ─── Chamada principal ───────────────────────────────────────────────────────

def chamar_webservice(
    operacao: str,
    xml_assinado: str,
    cert: CertificadoCarregado
) -> dict:
    """
    Executa uma chamada SOAP ao WebService NFS-e de João Pessoa.

    Suporta dois modos automaticamente conforme AMBIENTE no .env:
      - homologacao → GissOnline (nfseDadosMsg como string)
      - producao    → Receita JP (XML direto no body)

    Args:
        operacao:    nome interno da operação (ex: "ConsultarNfseFaixa")
        xml_assinado: XML com assinatura digital (ex: <ConsultarNfseFaixaEnvio>...)
        cert:        objeto CertificadoCarregado com chave e certificado PEM

    Returns:
        dict com sucesso, xml_enviado, xml_resposta, status_code, erro
    """
    service_url = _get_service_url()
    operacoes = _get_operacoes()
    ambiente = _get_ambiente()

    # Traduzir nome interno → nome WSDL do serviço ativo
    nome_wsdl = operacoes.get(operacao, operacao)
    if nome_wsdl != operacao:
        logger.info(
            f"[{ambiente.upper()}] Mapeando operação '{operacao}' → '{nome_wsdl}'"
        )

    soap_envelope, soapaction = _build_soap_envelope(nome_wsdl, xml_assinado)

    # Arquivos PEM temporários para mTLS
    cert_file = tempfile.NamedTemporaryFile(delete=False, suffix="_cert.pem", prefix="nfse_")
    cert_file.write(cert.cert_pem)
    cert_file.close()

    key_file = tempfile.NamedTemporaryFile(delete=False, suffix="_key.pem", prefix="nfse_")
    key_file.write(cert.key_pem)
    key_file.close()

    try:
        logger.info(
            f"[{ambiente.upper()}] Chamando: {service_url} | Operação: {nome_wsdl}"
        )

        response = requests.post(
            service_url,
            data=soap_envelope.encode("utf-8"),
            headers={
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": soapaction,
            },
            cert=(cert_file.name, key_file.name),
            verify=True,
            timeout=60
        )

        xml_resposta = _parse_soap_response(response.text, nome_wsdl)

        if response.status_code == 200:
            return {
                "sucesso": True,
                "xml_enviado": xml_assinado,
                "xml_resposta": xml_resposta,
                "status_code": response.status_code,
                "erro": None
            }
        else:
            return {
                "sucesso": False,
                "xml_enviado": xml_assinado,
                "xml_resposta": xml_resposta,
                "status_code": response.status_code,
                "erro": f"Servidor retornou HTTP {response.status_code}"
            }

    except requests.exceptions.Timeout:
        raise Exception("Timeout: o WebService não respondeu em 60 segundos.")
    except requests.exceptions.SSLError as e:
        raise Exception(f"Erro SSL: Verifique o certificado digital. Detalhe: {e}")
    except requests.exceptions.ConnectionError as e:
        raise Exception(
            f"Falha de conexão com o WebService ({service_url}). "
            f"Verifique a conectividade de rede. Detalhe: {e}"
        )
    finally:
        try:
            os.unlink(cert_file.name)
            os.unlink(key_file.name)
        except Exception:
            pass
