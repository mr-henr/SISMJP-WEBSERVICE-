"""
Cliente SOAP para o webservice SISMJP (João Pessoa - ABRASF 2.03).

Usa zeep com transport autenticado por certificado digital ICP-Brasil A1.
Implementado como singleton para reutilizar a conexão entre chamadas.
"""

import logging

from lxml import etree
from zeep import Client
from zeep.exceptions import Fault
from zeep.plugins import HistoryPlugin
from zeep.transports import Transport

from config.settings import (
    CERT_PATH,
    CERT_PASSWORD,
    WEBSERVICE_TIMEOUT,
    WEBSERVICE_OPERATION_TIMEOUT,
    WEBSERVICE_URL,
    WSDL_EFETIVO,
    WSDL_URL,
)
from utils.cert_utils import build_certified_session

_SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"

# Suprime logs verbosos do zeep/urllib3 em produção
logging.getLogger("zeep").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)


class WebserviceClient:
    """
    Wrapper do zeep.Client com autenticação por certificado A1.

    Expõe o proxy de serviço SOAP via .service e métodos utilitários
    para debug (último XML enviado/recebido).
    """

    def __init__(self):
        self._session = build_certified_session(CERT_PATH, CERT_PASSWORD)
        self._history = HistoryPlugin()

        transport = Transport(
            session=self._session,
            timeout=WEBSERVICE_TIMEOUT,
            operation_timeout=WEBSERVICE_OPERATION_TIMEOUT,
        )

        self._client = Client(
            wsdl=WSDL_EFETIVO,
            transport=transport,
            plugins=[self._history],
        )
        self._service = self._client.service

    @property
    def service(self):
        """Proxy de serviço zeep — use para chamar operações SOAP."""
        return self._service

    def get_last_sent_xml(self) -> str:
        """Retorna o XML do último envelope SOAP enviado (para debug)."""
        try:
            from lxml import etree
            return etree.tostring(
                self._history.last_sent["envelope"],
                pretty_print=True,
                encoding="unicode",
            )
        except Exception:
            return ""

    def get_last_received_xml(self) -> str:
        """Retorna o XML do último envelope SOAP recebido (para debug)."""
        try:
            from lxml import etree
            return etree.tostring(
                self._history.last_received["envelope"],
                pretty_print=True,
                encoding="unicode",
            )
        except Exception:
            return ""

    def call_raw(self, dados_xml: str, soap_action: str = "") -> str:
        """
        Envia envelope SOAP 1.1 bruto com o XML assinado no corpo.

        Usado em vez de client.service.*() porque o webservice de JP usa
        binding tipado (parâmetros como objetos) — não aceita nfseDadosMsg
        como string. Com call_raw, controlamos o XML exato enviado e o
        XMLDSig é preservado intacto.

        Args:
            dados_xml: XML assinado (ex: ConsultarNfseServicoPrestadoEnvio)
            soap_action: Valor do header SOAPAction (vazio = padrão ABRASF)

        Returns:
            Conteúdo do <Body> da resposta SOAP como string XML.

        Raises:
            zeep.exceptions.Fault: Se o servidor retornar um SOAP Fault.
            requests.exceptions.HTTPError: Para erros HTTP não-SOAP.
        """
        envelope = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<soapenv:Envelope xmlns:soapenv="{_SOAP_NS}">'
            "<soapenv:Header/>"
            "<soapenv:Body>"
            + dados_xml
            + "</soapenv:Body>"
            "</soapenv:Envelope>"
        )

        self._last_raw_sent: str = envelope
        self._last_raw_received: str = ""

        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": f'"{soap_action}"',
        }

        resp = self._session.post(
            WEBSERVICE_URL,
            data=envelope.encode("utf-8"),
            headers=headers,
            timeout=WEBSERVICE_OPERATION_TIMEOUT,
        )
        self._last_raw_received = resp.text

        # Tenta parsear como XML antes de checar o status HTTP (SOAP Faults
        # chegam como HTTP 500 mas contêm um body útil)
        try:
            root = etree.fromstring(resp.content)
        except etree.XMLSyntaxError:
            resp.raise_for_status()
            return resp.text

        # SOAP Fault?
        fault_el = root.find(f".//{{{_SOAP_NS}}}Fault")
        if fault_el is not None:
            code = fault_el.findtext("faultcode") or ""
            msg = fault_el.findtext("faultstring") or ""
            detail_el = fault_el.find("detail")
            detail = etree.tostring(detail_el, encoding="unicode") if detail_el is not None else ""
            raise Fault(message=f"{code}: {msg}", detail=detail)

        resp.raise_for_status()

        # Retorna o primeiro filho do Body
        body = root.find(f"{{{_SOAP_NS}}}Body")
        if body is not None and len(body) > 0:
            return etree.tostring(body[0], encoding="unicode")
        return resp.text

    def get_last_raw_sent(self) -> str:
        """Retorna o último envelope SOAP bruto enviado via call_raw (para debug)."""
        return getattr(self, "_last_raw_sent", "")

    def get_last_raw_received(self) -> str:
        """Retorna o último response bruto recebido via call_raw (para debug)."""
        return getattr(self, "_last_raw_received", "")

    def close(self):
        """Libera arquivos temporários do certificado."""
        if hasattr(self._session, "_cert_ctx"):
            self._session._cert_ctx.cleanup()


# ── Singleton ─────────────────────────────────────────────────────────────────

_client_instance: WebserviceClient | None = None


def get_client() -> WebserviceClient:
    """
    Retorna a instância singleton do WebserviceClient.

    Inicializa na primeira chamada (carrega WSDL + valida certificado).
    Reutiliza a mesma instância em chamadas subsequentes.

    Raises:
        FileNotFoundError: Se o certificado não for encontrado
        ValueError: Se a senha do certificado estiver errada
        SystemExit: Se houver falha SSL irrecuperável
    """
    global _client_instance
    if _client_instance is None:
        try:
            _client_instance = WebserviceClient()
        except Exception as exc:
            err_str = str(exc).lower()

            # DNS / conectividade
            if "getaddrinfo" in err_str or "nameresolution" in err_str or "name or service not known" in err_str:
                raise SystemExit(
                    "\n[REDE] Não foi possível resolver o hostname do webservice.\n"
                    "Causas mais comuns:\n"
                    "  1. Sem acesso à internet ou o servidor está fora do ar\n"
                    "  2. O servidor pode exigir VPN ou rede específica\n"
                    "  3. Solução alternativa: baixe o WSDL manualmente no browser e\n"
                    "     salve em wsdl/nfse.wsdl (o sistema usará o arquivo local)\n"
                    f"     URL do WSDL: {WSDL_URL}\n"
                    f"Erro original: {exc}"
                ) from exc

            # SSL / certificado
            if "ssl" in err_str or "certificate" in err_str or "cert" in err_str:
                raise SystemExit(
                    "\n[CERT] Falha de SSL/certificado ao inicializar o webservice.\n"
                    "Verifique:\n"
                    "  - CERT_PATH aponta para o arquivo .pfx correto\n"
                    "  - CERT_PASSWORD está correto\n"
                    "  - Os CAs ICP-Brasil estão instalados\n"
                    f"Erro original: {exc}"
                ) from exc

            # Timeout
            if "timeout" in err_str or "timed out" in err_str:
                raise SystemExit(
                    "\n[TIMEOUT] O servidor não respondeu no tempo limite.\n"
                    "O webservice pode estar lento ou inacessível.\n"
                    f"Erro original: {exc}"
                ) from exc

            raise
    return _client_instance
