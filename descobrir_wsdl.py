"""
Script de diagnóstico para descobrir a URL correta do webservice SISMJP.

Testa múltiplas URLs candidatas usando o certificado digital configurado no .env.
O motivo: o servidor pode retornar 404 sem certificado mas 200 com ele (mTLS).

Uso:
    python descobrir_wsdl.py

Resultado esperado: URL com status 200 e conteúdo XML (WSDL encontrado).
"""

import sys
import os

# Adiciona a pasta do projeto ao path para importar os módulos
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import urllib3
import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from config.settings import CERT_PATH, CERT_PASSWORD
from utils.cert_utils import load_pfx, TempCertContext

# ── URLs candidatas a testar ──────────────────────────────────────────────────
# Organizadas por probabilidade (mais provável primeiro)

CANDIDATAS = [
    # ── receita.joaopessoa.pb.gov.br — servidor confirmado de produção ────────
    # Padrões CXF/JAX-WS (Apache CXF expõe em /services/ ou diretamente)
    "https://receita.joaopessoa.pb.gov.br/notafiscal/services/NfseWS?wsdl",
    "https://receita.joaopessoa.pb.gov.br/notafiscal/NfseWS?wsdl",
    "https://receita.joaopessoa.pb.gov.br/notafiscal/NfseService?wsdl",
    "https://receita.joaopessoa.pb.gov.br/notafiscal/services/NfseService?wsdl",
    "https://receita.joaopessoa.pb.gov.br/notafiscal/webservice?wsdl",
    "https://receita.joaopessoa.pb.gov.br/notafiscal/webservice/NfseWS?wsdl",
    # Padrões com NfseWSService (testados antes sem cert)
    "https://receita.joaopessoa.pb.gov.br/notafiscal/NfseWSService?wsdl",
    "https://receita.joaopessoa.pb.gov.br/notafiscal/ws/NfseWSService?wsdl",
    "https://receita.joaopessoa.pb.gov.br/notafiscal/services/NfseWSService?wsdl",
    # Padrões Metro/JAX-WS no contexto raiz
    "https://receita.joaopessoa.pb.gov.br/NfseWS?wsdl",
    "https://receita.joaopessoa.pb.gov.br/sismjp/NfseWS?wsdl",
    "https://receita.joaopessoa.pb.gov.br/sismjp/NfseWSService?wsdl",
    # ── Tomcat porta 8443 (pode não estar atrás do Apache) ────────────────────
    "https://receita.joaopessoa.pb.gov.br:8443/notafiscal/NfseWS?wsdl",
    "https://receita.joaopessoa.pb.gov.br:8443/notafiscal/services/NfseWS?wsdl",
    "https://receita.joaopessoa.pb.gov.br:8443/notafiscal/NfseWSService?wsdl",
    "https://receita.joaopessoa.pb.gov.br:8443/sismjp/NfseWSService?wsdl",
    # ── serem-hml.joaopessoa.pb.gov.br — homologação ─────────────────────────
    "https://serem-hml.joaopessoa.pb.gov.br/notafiscal/services/NfseWS?wsdl",
    "https://serem-hml.joaopessoa.pb.gov.br/notafiscal/NfseWS?wsdl",
    "https://serem-hml.joaopessoa.pb.gov.br/notafiscal/NfseWSService?wsdl",
    "https://serem-hml.joaopessoa.pb.gov.br/notafiscal/NfseService?wsdl",
    "https://serem-hml.joaopessoa.pb.gov.br/sismjp/NfseWSService?wsdl",
]


def testar_com_certificado():
    print("\n" + "=" * 65)
    print("  SISMJP — Descoberta do endpoint do Webservice")
    print("=" * 65)
    print(f"\nCertificado: {CERT_PATH}")

    try:
        key_pem, cert_pem, _ = load_pfx(CERT_PATH, CERT_PASSWORD)
    except FileNotFoundError:
        print(f"\n[ERRO] Certificado não encontrado: {CERT_PATH}")
        print("       Verifique CERT_PATH e CERT_PASSWORD no .env")
        sys.exit(1)
    except ValueError as e:
        print(f"\n[ERRO] Falha ao carregar certificado: {e}")
        sys.exit(1)

    ctx = TempCertContext(key_pem, cert_pem)
    cert_file, key_file = ctx.setup()

    session = requests.Session()
    session.cert = (cert_file, key_file)
    session.verify = False  # Desabilitado para diagnóstico (CA ICP-Brasil pode não estar instalada)

    print(f"\nTestando {len(CANDIDATAS)} URLs...\n")
    print(f"{'Status':<10} {'URL'}")
    print("-" * 65)

    encontradas = []

    for url in CANDIDATAS:
        try:
            r = session.get(url, timeout=15, allow_redirects=True)
            status = r.status_code
            conteudo = r.text[:300] if r.text else ""

            is_wsdl = (
                status == 200 and (
                    "definitions" in conteudo.lower() or
                    "wsdl" in conteudo.lower() or
                    "<?xml" in conteudo.lower()
                )
            )

            if is_wsdl:
                print(f"[{status}] WSDL ENCONTRADO -> {url}")
                encontradas.append(url)
            elif status == 200:
                print(f"[{status}] Resposta 200 mas não parece WSDL -> {url}")
                print(f"           Conteúdo: {conteudo[:80].strip()}")
                encontradas.append(url)
            elif status == 404:
                print(f"[{status}]    Not Found -> {url}")
            elif status == 403:
                print(f"[{status}] Forbidden (existe mas acesso negado) -> {url}")
                encontradas.append(url)
            elif status == 401:
                print(f"[{status}] Unauthorized (existe, requer auth) -> {url}")
                encontradas.append(url)
            else:
                print(f"[{status}]    -> {url}")
                if conteudo:
                    print(f"           Conteúdo: {conteudo[:80].strip()}")

        except requests.exceptions.Timeout:
            print(f"[TIMEOUT]  -> {url}")
        except requests.exceptions.ConnectionError:
            print(f"[CONN ERR] Porta fechada/bloqueada -> {url}")
        except Exception as e:
            print(f"[ERRO]     {url} -> {str(e)[:60]}")

    ctx.cleanup()

    print("\n" + "=" * 65)
    if encontradas:
        print(f"\nURLs que responderam ({len(encontradas)}):")
        for u in encontradas:
            print(f"   {u}")
        print("\nAtualize WEBSERVICE_URL_PROD em config/settings.py com a URL correta.")
    else:
        print("\nNenhuma URL respondeu positivamente com o certificado.")
        print("   Possíveis causas:")
        print("   1. O webservice só é acessível dentro da rede da prefeitura (VPN)")
        print("   2. É necessário cadastrar o IP da sua máquina junto à SEREM")
        print("   3. O webservice ainda não está disponível publicamente")
        print("\n   Sugestão: entre em contato com o suporte da SEREM/Prefeitura")
        print("   para solicitar acesso ao webservice NFS-e.")
    print()


if __name__ == "__main__":
    testar_com_certificado()
