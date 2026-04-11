import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Carrega variáveis do .env (se existir)
load_dotenv()

# ── Diretório raiz do projeto ───────────────────────────────────────────────
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

# ── Webservice SISMJP ───────────────────────────────────────────────────────
WEBSERVICE_URL_PROD = "https://sispmjp.joaopessoa.pb.gov.br:8443/sispmjp/NfseWSService"
WEBSERVICE_URL_HOMOLOG = "https://nfsehomolog.joaopessoa.pb.gov.br:8443/sispmjp/NfseWSService"

USE_HOMOLOG = os.getenv("USE_HOMOLOG", "false").lower() == "true"
WEBSERVICE_URL = WEBSERVICE_URL_HOMOLOG if USE_HOMOLOG else WEBSERVICE_URL_PROD
WSDL_URL = f"{WEBSERVICE_URL}?wsdl"

# Versão do padrão ABRASF
ABRASF_VERSION = "2.03"
# Código IBGE de João Pessoa-PB
CODIGO_MUNICIPIO = "2507507"

# ── Certificado Digital ICP-Brasil A1 ──────────────────────────────────────
CERT_PATH = os.getenv("CERT_PATH", "")
CERT_PASSWORD = os.getenv("CERT_PASSWORD", "")

# ── Planilha de empresas ────────────────────────────────────────────────────
SPREADSHEET_PATH = BASE_DIR / "services" / "Auto_Prefeitura.xlsx"

# ── Pasta de saída ──────────────────────────────────────────────────────────
OUTPUT_BASE_PATH = os.getenv("OUTPUT_BASE_PATH", str(BASE_DIR / "output"))

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
