import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Carrega variáveis do .env (se existir)
load_dotenv()

# ── Diretório raiz do projeto ───────────────────────────────────────────────
# BASE_DIR aponta para a pasta sismjp-webservice/ (pai de config/)
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent


def _resolver_caminho(valor: str, padrao_relativo: Path) -> Path:
    """
    Resolve um caminho de configuração:
      - Se vazio → usa padrao_relativo (relativo a BASE_DIR)
      - Se relativo → resolve em relação a BASE_DIR
      - Se absoluto → usa como está

    Isso permite que o .env use tanto caminhos relativos simples
    ("certs/contador.pfx") quanto caminhos absolutos quando necessário.
    """
    if not valor:
        return padrao_relativo
    p = Path(valor)
    return p if p.is_absolute() else BASE_DIR / p


# ── Webservice SISMJP ───────────────────────────────────────────────────────
WEBSERVICE_URL_PROD = "https://sispmjp.joaopessoa.pb.gov.br:8443/sispmjp/NfseWSService"
WEBSERVICE_URL_HOMOLOG = "https://nfsehomolog.joaopessoa.pb.gov.br:8443/sispmjp/NfseWSService"

USE_HOMOLOG = os.getenv("USE_HOMOLOG", "false").lower() == "true"
WEBSERVICE_URL = WEBSERVICE_URL_HOMOLOG if USE_HOMOLOG else WEBSERVICE_URL_PROD
WSDL_URL = f"{WEBSERVICE_URL}?wsdl"

# ── WSDL local (opcional) ────────────────────────────────────────────────────
# Se existir o arquivo wsdl/nfse.wsdl, ele é usado no lugar do WSDL remoto.
# Útil quando o endpoint é inacessível ou para evitar download a cada execução.
# Para gerar: acesse {WSDL_URL} no browser e salve como wsdl/nfse.wsdl
_WSDL_LOCAL = _resolver_caminho(
    os.getenv("WSDL_LOCAL_PATH", ""),
    BASE_DIR / "wsdl" / "nfse.wsdl",
)
WSDL_EFETIVO = f"file:///{_WSDL_LOCAL}".replace("\\", "/") if _WSDL_LOCAL.exists() else WSDL_URL

# Versão do padrão ABRASF
ABRASF_VERSION = "2.03"
# Código IBGE de João Pessoa-PB
CODIGO_MUNICIPIO = "2507507"

# ── Certificado Digital ICP-Brasil A1 (do contador) ───────────────────────
# Um único certificado do contador com procuração das empresas.
# Caminho relativo a BASE_DIR ou absoluto. Ex: "certs/contador.pfx"
CERT_PATH = str(_resolver_caminho(os.getenv("CERT_PATH", ""), BASE_DIR / "certs" / "contador.pfx"))
CERT_PASSWORD = os.getenv("CERT_PASSWORD", "")

# ── Planilha de empresas ────────────────────────────────────────────────────
# Relativa a BASE_DIR. Ex: "services/Auto_Prefeitura.xlsx"
SPREADSHEET_PATH = _resolver_caminho(
    os.getenv("SPREADSHEET_PATH", ""),
    BASE_DIR / "services" / "Auto_Prefeitura.xlsx",
)

# ── Pasta de saída ──────────────────────────────────────────────────────────
# Relativa a BASE_DIR por padrão. Ex: "output" ou caminho absoluto de rede.
OUTPUT_BASE_PATH = str(_resolver_caminho(
    os.getenv("OUTPUT_BASE_PATH", ""),
    BASE_DIR / "output",
))

# ── SIEG ─────────────────────────────────────────────────────────────────────
SIEG_API_KEY = os.getenv("SIEG_API_KEY", "")
SIEG_UPLOAD_URL = "https://up.sieg.com/EnviarXml"

# ── NIBO ─────────────────────────────────────────────────────────────────────
NIBO_API_KEY = os.getenv("NIBO_API_KEY", "")
NIBO_ACCOUNTING_FIRM_ID = os.getenv("NIBO_ACCOUNTING_FIRM_ID", "")
NIBO_USER_ID = os.getenv("NIBO_USER_ID", "")
NIBO_BASE_URL = "https://api.nibo.com.br/accountant/api/v1"

# ── Parâmetros de processamento ──────────────────────────────────────────────
# Número de meses retroativos a consultar
RETROACTIVE_MONTHS = 6

# Timeout para chamadas SOAP (segundos)
WEBSERVICE_TIMEOUT = 60
WEBSERVICE_OPERATION_TIMEOUT = 120
