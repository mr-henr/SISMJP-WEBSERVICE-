"""
Cliente SOAP para o webservice SISMJP (João Pessoa - ABRASF 2.03).

Usa zeep com transport autenticado por certificado digital ICP-Brasil A1.
Implementado como singleton para reutilizar a conexão entre chamadas.
"""

import logging

from zeep import Client
from zeep.plugins import HistoryPlugin
from zeep.transports import Transport

from config.settings import (
    CERT_PATH,
    CERT_PASSWORD,
    WEBSERVICE_TIMEOUT,
    WEBSERVICE_OPERATION_TIMEOUT,
    WSDL_EFETIVO,
    WSDL_URL,
)
from utils.cert_utils import build_certified_session

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
