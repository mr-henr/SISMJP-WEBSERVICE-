# 🌳 Relatório do Projeto: automacao-prefeitura

**Diretório Raiz:** `C:/Drive Contattus/OneDrive/T.I/Projetos/automacao-prefeitura`
**Data da Varredura:** 08/04/2026 11:40:06

## 🏗️ Estrutura de Arquivos

```
📁 automacao-prefeitura/
├── 📄 main.py
├── 📁 APIs/
│   ├── 📄 NIBO-Conferencia.py
│   ├── 📄 SIEG_API.py
├── 📁 config/
│   ├── 📄 settings.py
│   ├── 📄 __init__.py
├── 📁 logs/
├── 📁 services/
│   ├── 📄 authentication_service.py
│   ├── 📄 fiscal_book_service.py
│   ├── 📄 info_service.py
│   ├── 📄 logging_service.py
│   ├── 📄 nfse_service.py
│   ├── 📄 retroactive_service.py
│   ├── 📄 selection_service.py
│   ├── 📄 __init__.py
├── 📁 utils/
│   ├── 📄 error_handling.py
│   ├── 📄 file_utils.py
│   ├── 📄 menu_utils.py
│   ├── 📄 playwright_utils.py
│   ├── 📄 __init__.py
```


---

## 📜 Conteúdo dos Arquivos

### 📄 `main.py`

```python
import sys
import io
import os
from playwright.sync_api import sync_playwright
from config.settings import LOGIN_CREDENTIALS
from utils.playwright_utils import install_playwright_browsers, inicializar_playwright
from services.authentication_service import fazer_login
from services.info_service import carregar_empresa, carregar_path_base
from utils.file_utils import limpar_nome
from services.selection_service import garantir_contexto, selecionar_empresa
from utils.menu_utils import gerenciar_nfse, livrofiscal_menu, nfse_menu
from services.fiscal_book_service import livro_fiscal_competencia, livro_fiscal_download
from services.nfse_service import nsfe_competencia, nsfe_download
from services.retroactive_service import consulta_retroativa
from services.logging_service import log_error, log_warning, log_info
from pathlib import Path
import locale
from APIs.SIEG_API import upload_all_nfse_after_run


# Configurar encoding para UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def main():
    try:
        try:
            locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
        except Exception:
            try:
                locale.setlocale(locale.LC_ALL, 'C.UTF-8')
            except Exception:
                pass
        base_dir = Path(__file__).parent
        planilha_path = base_dir / "services" / "Auto_Prefeitura.xlsx"
        
        codigos, nomes_empresas, cnpj_cpf = carregar_empresa(planilha_path)
        pasta_base, comp_path, competencia = carregar_path_base(planilha_path)
        
        with sync_playwright() as pw:
            install_playwright_browsers()
            page = inicializar_playwright(pw)
            fazer_login(page, LOGIN_CREDENTIALS)

            for i in range(len(codigos)):
                try:
                    current_codigo = codigos[i]
                    current_nome_empresa = limpar_nome(nomes_empresas[i])
                    current_cnpj_cpf = cnpj_cpf[i]
                    
                    log_info(current_nome_empresa, current_codigo, "Início", "Iniciando processamento para empresa")
                    print(f"\n[EMPRESA] 🔄 Iniciando processamento para: '{current_nome_empresa}'")
                    
                    garantir_contexto(page)
                    
                    selecao_sucesso = selecionar_empresa(page, current_codigo, current_nome_empresa, current_cnpj_cpf)
                    if not selecao_sucesso:
                        log_warning(current_nome_empresa, current_codigo, "Seleção", f"Nenhum cadastro encontrado com CNPJ/CPF: {current_cnpj_cpf}")
                        print(f"[SELECAO] Nenhum cadastro encontrado para a empresa '{current_nome_empresa}' com CNPJ/CPF: {current_cnpj_cpf}")
                        print(f"[ERRO] A automação para '{current_nome_empresa}' será pulada. Prosseguindo para a próxima empresa (se houver).")
                        continue
                        
                    # Resto do processamento para empresas encontradas
                    gerenciar_nfse(page, i)
                    livrofiscal_menu(page)
                    livro_fiscal_competencia(page, "Prestador", competencia)
                    livro_fiscal_download(page, "Prestador", competencia, current_nome_empresa, comp_path, pasta_base, current_codigo)
                    livro_fiscal_download(page, "Tomador", competencia, current_nome_empresa, comp_path, pasta_base, current_codigo)
                    nfse_menu(page, current_nome_empresa)
                    nsfe_competencia(page, competencia)
                    nsfe_download(page, current_nome_empresa, "Recebidas", pasta_base, comp_path, competencia, current_codigo)
                    nsfe_download(page, current_nome_empresa, "Emitidas", pasta_base, comp_path, competencia, current_codigo)
                    
                    # Nova etapa: Consulta Retroativa
                    consulta_retroativa(page, competencia, pasta_base, current_codigo, current_nome_empresa, comp_path)

                    log_info(current_nome_empresa, current_codigo, "Conclusão", "Processamento concluído com sucesso")
                    
                except Exception as e:
                    log_error(current_nome_empresa, current_codigo, "Processamento Geral", str(e), {"CNPJ/CPF": current_cnpj_cpf})
                    print(f"[ERRO] ❌ Ocorreu um erro crítico durante o processamento da empresa '{current_nome_empresa}': {e}")
                    print(f"[ERRO] A automação para '{current_nome_empresa}' será pulada. Prosseguindo para a próxima empresa (se houver).")
                    continue

        # ✅ AQUI: fora do Playwright, depois de processar todas as empresas
        api_key = os.getenv("SIEG_API_KEY")
        if not api_key:
            print("[SIEG] ⚠️ Variável de ambiente SIEG_API_KEY não definida. Upload para o SIEG foi ignorado.")
        else:
            print("\n[SIEG] 🚀 Iniciando upload pós-processamento (NFSe) para o SIEG...")
            upload_all_nfse_after_run(
                api_key=api_key,
                pasta_base=pasta_base,
                timeout=60,
                double_encode_api_key=False,  # se der 401, troque pra True
                retries=3,
                retry_backoff_sec=2.0,
                fail_fast=False,
            )
            
    except Exception as e: 
        log_error("Sistema", "N/A", "Processamento Geral", f"Erro geral: {e}")
        print(f"Erro geral: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

### 📄 `APIs\NIBO-Conferencia.py`

```python
import os
import shutil
import requests
import logging

# --- CONFIGURAÇÕES ---
# Substitua pelas suas credenciais reais do Nibo Obrigações
API_KEY = "SUA_API_KEY_AQUI"
# O ID do escritório ou organização geralmente é necessário no header ou URL
ACCOUNTING_FIRM_ID = "SEU_ID_ESCRITORIO"
# O ID do usuário é frequentemente exigido na API do Contador/Obrigações
USER_ID = "SEU_ID_USUARIO"

# URLs da API (Verifique na documentação oficial se a versão é v1 ou outra)
# Nota: O Nibo tem APIs diferentes para Empresa e Obrigações. 
# Base URL correta para Nibo Obrigações (Contador)
BASE_URL = "https://api.nibo.com.br/accountant/api/v1" 

# Pastas Locais (Use caminhos locais, fora do OneDrive se possível, para evitar conflitos de sincronização)
PASTA_ORIGEM = r"C:\Automacao\Prefeitura\Arquivos"
PASTA_PROCESSADOS = r"C:\Automacao\Prefeitura\Processados"
PASTA_ERRO = r"C:\Automacao\Prefeitura\Erros"

# Configuração de Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

def setup_folders():
    """Cria as pastas de destino se não existirem."""
    if not os.path.exists(PASTA_PROCESSADOS):
        os.makedirs(PASTA_PROCESSADOS)
    if not os.path.exists(PASTA_ERRO):
        os.makedirs(PASTA_ERRO)

def upload_file_to_nibo(filepath):
    """
    Etapa 1: Faz o upload do arquivo físico para o servidor do Nibo.
    Retorna o ID do arquivo gerado pelo Nibo.
    """
    # Endpoint de upload vinculado ao escritório
    url = f"{BASE_URL}/accountingfirms/{ACCOUNTING_FIRM_ID}/files"
    filename = os.path.basename(filepath)
    
    headers = {
        "X-API-Key": API_KEY,
        "X-User-Id": USER_ID,
        # Content-Type geralmente não é definido manualmente ao usar 'files' no requests, 
        # pois a lib define o boundary do multipart/form-data automaticamente.
    }
    
    # Abre o arquivo em modo binário
    with open(filepath, 'rb') as f:
        files = {'file': (filename, f)}
        try:
            logger.info(f"Iniciando upload de: {filename}")
            response = requests.post(url, headers=headers, files=files)
            response.raise_for_status()
            
            # O Nibo retorna um JSON com o ID do arquivo, ex: {"id": "123-abc-..."}
            file_data = response.json()
            return file_data.get('id')
            
        except Exception as e:
            logger.error(f"Erro no upload do arquivo {filename}: {e}")
            if response:
                logger.error(f"Detalhe da resposta: {response.text}")
            return None

def send_to_conference(file_id, filename):
    """
    Etapa 2: Vincula o arquivo enviado à tela de Conferência.
    """
    # Endpoint específico para enviar para a Conferência
    url = f"{BASE_URL}/accountingfirms/{ACCOUNTING_FIRM_ID}/conferences"
    
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY,
        "X-User-Id": USER_ID
    }
    
    payload = {
        "fileId": file_id
    }
    
    try:
        logger.info(f"Enviando arquivo {file_id} para a Conferência...")
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        logger.info(f"Sucesso! Arquivo {filename} está na Conferência.")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao enviar para conferência: {e}")
        if response:
            logger.error(f"Detalhe da resposta: {response.text}")
        return False

def process_files():
    setup_folders()
    
    # Lista todos os arquivos na pasta de origem
    arquivos = [f for f in os.listdir(PASTA_ORIGEM) if os.path.isfile(os.path.join(PASTA_ORIGEM, f))]
    
    if not arquivos:
        logger.info("Nenhum arquivo encontrado para processar.")
        return

    for arquivo in arquivos:
        caminho_completo = os.path.join(PASTA_ORIGEM, arquivo)
        
        # 1. Upload
        file_id = upload_file_to_nibo(caminho_completo)
        
        if file_id:
            # 2. Enviar para Conferência
            sucesso = send_to_conference(file_id, arquivo)
            
            if sucesso:
                # Move para processados
                shutil.move(caminho_completo, os.path.join(PASTA_PROCESSADOS, arquivo))
            else:
                # Move para erro (Upload funcionou, mas conferência falhou)
                shutil.move(caminho_completo, os.path.join(PASTA_ERRO, arquivo))
        else:
            # Move para erro (Upload falhou)
            shutil.move(caminho_completo, os.path.join(PASTA_ERRO, arquivo))

if __name__ == "__main__":
    process_files()

```

### 📄 `APIs\SIEG_API.py`

```python
# APIs/SIEG_API.py
from __future__ import annotations

import base64
import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import quote

import requests

SIEG_UPLOAD_BASE_URL = "https://up.sieg.com/EnviarXml"

# ==========================
# CONFIG (opcional)
# ==========================
# Se você quiser deixar a ApiKey fixa no código (script privado), coloque aqui.
# Recomendação: use a chave CRUA (com + e =), não a versão %2b/%3d.
# Você ainda pode sobrescrever via variável de ambiente SIEG_API_KEY ou via --api_key.
DEFAULT_SIEG_API_KEY: str = "sFwq+8izbnuIJwTbscl7cg=="


@dataclass
class SiegUploadResult:
    ok: bool
    status_code: int
    url: str
    xml_path: str
    response_text: Optional[str] = None
    response_json: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


def _encode_api_key(api_key: str, double_encode: bool = False) -> str:
    """
    A doc do SIEG pede 'encode' da ApiKey.
    Normalmente: URL-encode.
    Se sua chave/teste exigir o padrão %252F (double-encode), ative double_encode=True.
    """
    api_key = (api_key or "").strip()
    if not api_key:
        raise ValueError("SIEG ApiKey vazia.")
    once = quote(api_key, safe="")
    return quote(once, safe="") if double_encode else once


def _xml_file_to_base64(xml_path: Union[str, Path]) -> str:
    raw = Path(xml_path).read_bytes()
    return base64.b64encode(raw).decode("ascii")


def _safe_json(text: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(text)
    except Exception:
        return None


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def upload_xml_file(
    api_key: str,
    xml_path: Union[str, Path],
    *,
    timeout: int = 60,
    double_encode_api_key: bool = False,
) -> SiegUploadResult:
    encoded_key = _encode_api_key(api_key, double_encode=double_encode_api_key)
    url = f"{SIEG_UPLOAD_BASE_URL}?api_key={encoded_key}"
    xml_b64 = _xml_file_to_base64(xml_path)

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
    }
    payload = {"Xml": xml_b64}

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        return SiegUploadResult(
            ok=False,
            status_code=0,
            url=url,
            xml_path=str(xml_path),
            error=f"Falha de rede/timeout: {e}",
        )

    text = resp.text or ""
    j = _safe_json(text)
    ok = 200 <= resp.status_code < 300

    err = None
    if not ok:
        msg = None
        if isinstance(j, dict):
            msg = j.get("message") or j.get("Message") or j.get("error") or j.get("Error")
        err = msg or f"HTTP {resp.status_code}"

    return SiegUploadResult(
        ok=ok,
        status_code=resp.status_code,
        url=url,
        xml_path=str(xml_path),
        response_text=text[:4000] if text else None,
        response_json=j if isinstance(j, dict) else None,
        error=err,
    )


# ==========================
# Pós-processamento (batch)
# ==========================

def _load_manifest(manifest_path: Path) -> Dict[str, Any]:
    if manifest_path.exists():
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return {"sent": {}}
    return {"sent": {}}


def _save_manifest(manifest_path: Path, manifest: Dict[str, Any]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def find_nfse_xmls(pasta_base: Union[str, Path]) -> List[Path]:
    """
    Varre Prestador/ e Tomador/ e pega os XMLs gerados pela sua automação.
    """
    base = Path(pasta_base)
    patterns = [
        "Prestador/**/XML_Emitidas-*.xml",
        "Tomador/**/XML_Recebidas-*.xml",
    ]
    files: List[Path] = []
    for pat in patterns:
        files.extend(base.glob(pat))
    return sorted(set(files))


def upload_all_nfse_after_run(
    api_key: str,
    *,
    pasta_base: Union[str, Path],
    timeout: int = 60,
    double_encode_api_key: bool = False,
    retries: int = 3,
    retry_backoff_sec: float = 2.0,
    manifest_filename: str = ".sieg_upload_manifest.json",
    fail_fast: bool = False,
) -> Dict[str, Any]:
    """
    Roda após a automação: encontra todos os XMLs NFSe e envia ao SIEG.
    Usa manifest (hash SHA256) pra evitar reenvio.
    """
    base = Path(pasta_base)
    manifest_path = base / manifest_filename
    manifest = _load_manifest(manifest_path)
    sent: Dict[str, Any] = manifest.get("sent", {})

    xmls = find_nfse_xmls(base)

    summary = {
        "total_found": len(xmls),
        "skipped_already_sent": 0,
        "sent_ok": 0,
        "sent_fail": 0,
        "fails": [],
    }

    print(f"[SIEG] Pós-processamento: encontrados {len(xmls)} XMLs NFSe para avaliar.")

    for p in xmls:
        try:
            digest = _sha256_file(p)
        except Exception as e:
            summary["sent_fail"] += 1
            summary["fails"].append({"file": str(p), "error": f"Falha ao ler/hash: {e}"})
            if fail_fast:
                break
            continue

        if digest in sent:
            summary["skipped_already_sent"] += 1
            continue

        last_err = None
        result: Optional[SiegUploadResult] = None

        for attempt in range(1, retries + 1):
            result = upload_xml_file(
                api_key=api_key,
                xml_path=p,
                timeout=timeout,
                double_encode_api_key=double_encode_api_key,
            )
            if result.ok:
                break

            last_err = result.error or "erro desconhecido"
            # Retry apenas em rede/timeout ou 5xx
            if result.status_code == 0 or (500 <= result.status_code <= 599):
                time.sleep(retry_backoff_sec * attempt)
                continue
            break  # 4xx não costuma resolver com retry

        if result and result.ok:
            summary["sent_ok"] += 1
            sent[digest] = {
                "file": str(p),
                "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                "status_code": result.status_code,
            }
            if summary["sent_ok"] % 10 == 0:
                _save_manifest(manifest_path, {"sent": sent})
            print(f"[SIEG] OK | HTTP {result.status_code} | {p}")
        else:
            summary["sent_fail"] += 1
            summary["fails"].append({
                "file": str(p),
                "error": last_err or "falha sem detalhes",
                "status_code": getattr(result, "status_code", None),
            })
            print(f"[SIEG] ERRO | {p} | {last_err}")
            if fail_fast:
                break

    _save_manifest(manifest_path, {"sent": sent})

    print(
        f"[SIEG] Finalizado: ok={summary['sent_ok']} "
        f"falhas={summary['sent_fail']} "
        f"pulados={summary['skipped_already_sent']} "
        f"encontrados={summary['total_found']}"
    )
    return summary


if __name__ == "__main__":
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Upload de XMLs (NFSe) para o Cofre SIEG")
    parser.add_argument(
        "--pasta_base",
        required=False,
        help="Pasta base onde estão as subpastas Prestador/Tomador (recursivo).",
    )
    parser.add_argument(
        "--api_key",
        required=False,
        help="ApiKey do SIEG (se não usar SIEG_API_KEY / DEFAULT_SIEG_API_KEY).",
    )
    parser.add_argument(
        "--double_encode",
        action="store_true",
        help="Força double URL-encode da ApiKey (use apenas se necessário).",
    )
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--fail_fast", action="store_true")
    args = parser.parse_args()

    # Prioridade: --api_key > env > DEFAULT
    api_key = (args.api_key or os.getenv("SIEG_API_KEY") or DEFAULT_SIEG_API_KEY or "").strip()
    if not api_key:
        print("[SIEG] ApiKey não informada. Use --api_key, SIEG_API_KEY ou DEFAULT_SIEG_API_KEY.")
        raise SystemExit(2)

    pasta_base = args.pasta_base or os.getenv("SIEG_PASTA_BASE")
    if not pasta_base:
        print("[SIEG] Informe --pasta_base (ou defina SIEG_PASTA_BASE).")
        raise SystemExit(2)

    summary = upload_all_nfse_after_run(
        api_key=api_key,
        pasta_base=pasta_base,
        timeout=args.timeout,
        double_encode_api_key=args.double_encode,
        retries=args.retries,
        retry_backoff_sec=2.0,
        fail_fast=args.fail_fast,
    )

    raise SystemExit(0 if summary["sent_fail"] == 0 else 1)
```

### 📄 `config\settings.py`

```python
###VERSÃO ORIGINAL
# import os
#from pathlib import Path

## Configurações de credenciais e processos
#PORTAL_URL = "https://receita.joaopessoa.pb.gov.br/notafiscal/paginas/login/login.jsf"
#LOGIN_CREDENTIALS = {
#    "username": "011.879.504-08",
#    "password": "123456",
#}

## Configurações de paths
#BASE_DIR = Path(__file__).resolve().parent.parent
#SPREADSHEET_PATH = BASE_DIR / "services" / "Auto_Prefeitura.xlsm"
#DOWNLOAD_BASE_PATH = "" 

## Configurações de tempo
#TIMEOUT = 30000
#SLOW_MO = 350
#SCREEN_SIZE = {"width": 1366, "height": 768}
#HEADLESS = False

from pathlib import Path
import sys

# Determinar o diretório base
if getattr(sys, 'frozen', False):
    # Executável empacotado
    BASE_DIR = Path(sys.executable).parent
else:
    # Desenvolvimento
    BASE_DIR = Path(__file__).resolve().parent.parent

# Configurações de credenciais e processos
PORTAL_URL = "https://receita.joaopessoa.pb.gov.br/notafiscal/paginas/login/login.jsf"
LOGIN_CREDENTIALS = {
    "username": "011.879.504-08",
    "password": "123456",
}

# Configurações de paths
SPREADSHEET_PATH = BASE_DIR / "services" / "Auto_Prefeitura.xlsx"
DOWNLOAD_BASE_PATH = "" 

# Configurações de tempo
TIMEOUT = 30000
SLOW_MO = 350
SCREEN_SIZE = {"width": 1366, "height": 768}
HEADLESS = False
```

### 📄 `config\__init__.py`

```python

```

### 📄 `services\authentication_service.py`

```python
from playwright.sync_api import Page


def fazer_login(page: Page, credentials: dict) -> None:
    """Realiza login no portal"""
    try:
        page.goto("https://receita.joaopessoa.pb.gov.br/notafiscal/paginas/login/login.jsf", 
                timeout=60000, wait_until="networkidle")
        
        print("[LOGIN] Realizando login no portal...")
        page.locator("[data-test=\"login\"]").click()
        page.locator("[data-test=\"login\"]").fill(credentials["username"])
        page.locator("[data-test=\"password\"]").click()
        page.locator("[data-test=\"password\"]").fill(credentials["password"])
        page.locator("[data-test=\"entrar\"]").click()
        
        # Aguarda redirecionamento
        page.wait_for_url(
            "https://receita.joaopessoa.pb.gov.br/notafiscal/paginas/selecionacadastro/selecionaCadastro.jsf", 
            wait_until="networkidle", 
            timeout=60000
        )

        
        print("[LOGIN] Login realizado com sucesso!")
    except Exception as e:
        print(f"[LOGIN] Erro ao realizar login: {e}")
```

### 📄 `services\fiscal_book_service.py`

```python
from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from pathlib import Path
from utils.error_handling import capturar_toast_erro
from utils.file_utils import limpar_arquivos_de_erro

def livro_fiscal_competencia(page: Page, PT, competencia):
    try:
        page.wait_for_load_state("load", timeout=90000)
        print(f"\n[LIVRO FISCAL] Iniciando coleta de Livro Fiscal - {PT}...")
        comp_ini_prest = page.locator('input[name$="idStart_input"]')
        print("[LOG] Clique Competencia Inicial")
        comp_fim_prest = page.locator('input[name$="idEnd_input"]')
        print("[LOG] Clique Competencia Final")
    except Exception as e:
        print(f"[ERRO] Falha na coleta de Livro Fiscal - {PT}: {e}")

    try:
        print(f"[LIVRO FISCAL] Preenchendo período de competência ({competencia}) para {PT}.")
        comp_ini_prest.click(timeout=3000)
        page.wait_for_timeout(200)
        comp_ini_prest.type(competencia)
        page.wait_for_timeout(200)
        comp_fim_prest.click()
        page.wait_for_timeout(200)
        comp_fim_prest.type(competencia)
        page.wait_for_timeout(200)
    except Exception:
        try:
            print("[ERRO] Falha ao selecionar competencia")
            print("[LOG] Tentando Novamente")
            print("[NAVEGADOR] Clicando em 'Gerenciar NFSe' no menu principal.")
            page.get_by_role("link", name="Gerenciar NFSe ").click()
            print("[NAVEGADOR] Clicando em 'Livro Fiscal' no menu de navegação.")
            locators = page.locator('span.nav-label', has_text="Livro Fiscal")
            print("[LOG] Clicando em Livro Fiscal")
            count = locators.count()
            for i in range(count):
                element = locators.nth(i)
                if element.is_visible():
                    element.click()
                    break
            print(f"[LIVRO FISCAL] Preenchendo período de competência ({competencia}) para {PT}.")
            comp_ini_prest.click()
            page.wait_for_timeout(200)
            comp_ini_prest.type(competencia)
            page.wait_for_timeout(200)
            comp_fim_prest.click()
            page.wait_for_timeout(200)
            comp_fim_prest.type(competencia)
            page.wait_for_timeout(200)
        except Exception:
            raise Exception ("[ERRO] Problema não solucionado na seleção de competência")
        


def tela_de_processamento(page: Page):
    try:
        page.wait_for_selector("div.swal-modal.jarch-messageprocess", state="visible", timeout=5000)
        print("[LOAD]🔄 Tela 'Processando...' apareceu. Aguardando sumir...")

        try:
            page.wait_for_selector("div.swal-modal.jarch-messageprocess", state="hidden", timeout=5000)
        except PlaywrightTimeoutError:
            print("[INFO]⚠️ A tela de 'Processando...' travou. Tentando forçar fechamento...")

            # Tenta forçar o fechamento via JavaScript
            page.evaluate("""
                () => {
                    // Remove modal de processamento
                    const modal = document.querySelector('div.swal-modal.jarch-messageprocess');
                    if (modal) {
                        modal.remove();
                    }

                    // Remove overlay de fundo escuro se existir
                    const backdrop = document.querySelector('.swal-overlay, .swal-backdrop, .swal2-backdrop, .swal2-container');
                    if (backdrop) {
                        backdrop.remove();
                    }

                    // Garante que o body volte ao normal
                    document.body.style.overflow = 'auto';
                    document.body.style.pointerEvents = 'auto';

                    // Garante que o html volte ao normal também
                    document.documentElement.style.overflow = 'auto';
                    document.documentElement.style.pointerEvents = 'auto';
                }
            """)
            page.wait_for_timeout(1000)
            print("[INFO] Tela 'Processando...' foi forçada a desaparecer.")
    except PlaywrightTimeoutError:
        print("ℹ️ Tela de 'Processando...'")

def livro_fiscal_download(page: Page, PT, competencia, current_nome_empresa, comp_path, pasta_base, current_codigo):
    if PT == "Prestador":
        print("[LIVRO FISCAL] Clicando em 'Download' para Livro Fiscal - Prestador.")
        botao_download = page.get_by_role("link", name=" Download")
        botao_download.wait_for(state="visible", timeout=15000)
        botao_download.hover()
        page.wait_for_timeout(500)  # Simula o tempo humano de interação
        botao_download.click()
        
        # Aguarda a tela de processamento aparecer
        tela_de_processamento(page)
        # Verifica se há mensagem de erro "Nenhum registro encontrado" para Prestador
        page.wait_for_load_state('load', timeout=20000)
        page.wait_for_timeout(3000)
        erro_Prest = capturar_toast_erro(page, current_nome_empresa, competencia, "Prestador", current_codigo, pasta_base, comp_path, Mensagem="Nenhum registro encontrado")
        if erro_Prest:
            print(f"[LIVRO FISCAL] Nenhum registro de Prestador encontrado para '{current_nome_empresa}' na competência '{competencia}'.")
        else:
            page.wait_for_timeout(2000)
            #verificação de duas etapas
            erro_Prest = capturar_toast_erro(page, current_nome_empresa, competencia, "Prestador", current_codigo, pasta_base, comp_path, Mensagem="Nenhum registro encontrado")
            if erro_Prest:
                print(f"[2][LIVRO FISCAL] Nenhum registro de Prestador encontrado para '{current_nome_empresa}' na competência '{competencia}'.")
            else:
                # Se não houver erro, tenta realizar o download do Livro Fiscal de Prestador
                with page.expect_download() as download_info:
                    botao_download.wait_for(state="visible", timeout=15000)
                    botao_download.hover()
                    page.wait_for_timeout(500)  # Simula o tempo humano de interação
                    botao_download.click() # Clica novamente no botão de download (pode ser necessário)
                download = download_info.value
                download_path_prest = Path(f"{pasta_base}/Prestador/{current_codigo}-{current_nome_empresa}/{comp_path}/{current_codigo}-{current_nome_empresa}.pdf")
                download_path_prest.parent.mkdir(parents=True, exist_ok=True) # Garante que o diretório exista
                download.save_as(download_path_prest)
                print(f"[LIVRO FISCAL] ✅ Livro Fiscal Prestador salvo em: {download_path_prest}")
                # Limpa arquivos de erro antigos da pasta, já que o download foi bem-sucedido
                limpar_arquivos_de_erro(download_path_prest.parent)
                page.wait_for_timeout(2000)
            # Aguarda a tela de processamento aparecer
            tela_de_processamento(page) 

    else:
        print("\n[LIVRO FISCAL] Iniciando coleta de Livro Fiscal - Tomador...")
        page.wait_for_timeout(500)
        # Clica para alternar para "Serviços Tomados"
        print("[LIVRO FISCAL] Selecionando 'Serviços Tomados' no agrupamento.")
        page.get_by_role("cell", name=" Livro Fiscal Agrupamento").locator("span").nth(2).click()
        page.wait_for_timeout(500)
        page.get_by_role("option", name="Serviços Tomados").click()

        # Clica no botão de Download para o Tomador
        print("[LIVRO FISCAL] Clicando em 'Download' para Livro Fiscal - Tomador.")
        page.get_by_role("link", name=" Download").click()
        # Aguarda a tela de processamento aparecer
        tela_de_processamento(page)
        page.wait_for_load_state("load", timeout=20000)
        page.wait_for_timeout(3000) # Pequena espera para o toast
        # Verifica se há mensagem de erro para Tomador
        erro_Tom = capturar_toast_erro(page, current_nome_empresa, competencia, "Tomador", current_codigo, pasta_base, comp_path, Mensagem="Nenhum registro encontrado")
        if erro_Tom:
            print(f"[LIVRO FISCAL] Nenhum registro de Tomador encontrado para '{current_nome_empresa}' na competência '{competencia}'.")
        else:
            page.wait_for_timeout(2000)
            erro_Tom = capturar_toast_erro(page, current_nome_empresa, competencia, "Tomador", current_codigo, pasta_base, comp_path, Mensagem="Nenhum registro encontrado")
            if erro_Tom:
                print(f"[2][LIVRO FISCAL] Nenhum registro de Tomador encontrado para '{current_nome_empresa}' na competência '{competencia}'.")
            else:
                # Se não houver erro, tenta realizar o download do Livro Fiscal de Tomador
                with page.expect_download(timeout=20000) as download_info:
                    page.get_by_role("link", name=" Download").click() # Clica novamente no botão de download
                download = download_info.value
                download_path_tom = Path(f"{pasta_base}/Tomador/{current_codigo}-{current_nome_empresa}/{comp_path}/{current_codigo}-{current_nome_empresa}.pdf")
                download_path_tom.parent.mkdir(parents=True, exist_ok=True) # Garante que o diretório exista
                download.save_as(download_path_tom)
                print(f"[LIVRO FISCAL] ✅ Livro Fiscal Tomador salvo em: {download_path_tom}")
                # Limpa arquivos de erro antigos da pasta, já que o download foi bem-sucedido
                limpar_arquivos_de_erro(download_path_tom.parent)
                tela_de_processamento(page)
        page.wait_for_timeout(1500)

```

### 📄 `services\info_service.py`

```python
import pandas as pd
from datetime import datetime


def carregar_empresa(caminho_planilha):
    """Lê a planilha e retorna os dados necessários"""
    try:
        # Ler todas as colunas como string para preservar formatação
        entradas = pd.read_excel(caminho_planilha, dtype=str)
        
        # Remover linhas completamente vazias e filtrar apenas linhas válidas
        entradas = entradas.dropna(how='all')  # Remove linhas completamente vazias
        
        # Filtrar apenas linhas onde 'PROCESSO' existe e é igual a 'S'
        # E também onde 'CODIGO' não é vazio
        empresas_participantes = entradas[
            (entradas['PROCESSO'].notna()) & 
            (entradas['PROCESSO'] == 'S') &
            (entradas['CODIGO'].notna())
        ]

        codigo = []
        nome_empresa = []
        cnpj_cpf = []
        
        for idx, row in empresas_participantes.iterrows():
            # Processar CODIGO
            cod = str(row['CODIGO']).strip()
            if cod and cod != 'nan':  # Ignorar valores vazios ou 'nan'
                if '.' in cod:
                    codigo.append(str(int(float(cod))))
                else:
                    codigo.append(cod)
                
                # Processar CLIENTE
                nome = str(row['CLIENTE']).strip() if pd.notna(row['CLIENTE']) else f"Empresa_{cod}"
                nome_empresa.append(nome)
                
                # Processar CNPJ/CPF
                cnpj = str(row['CNPJ / CPF']).strip() if pd.notna(row['CNPJ / CPF']) else ""
                cnpj_cpf.append(cnpj)
        
        return codigo, nome_empresa, cnpj_cpf
    except Exception as e:
        raise Exception(f"Erro ao ler planilha: {str(e)}")

def carregar_path_base(caminho_planilha):
    """Lê a planilha e retorna o caminho base e a competência"""
    try:
        df = pd.read_excel(caminho_planilha, header=None)
        
        # Preencher NaN com string vazia para evitar erros
        df = df.fillna('')
        
        pasta_base = str(df.iloc[0, 10]).strip()
        competencia_raw = df.iloc[4, 7]
        
        if isinstance(competencia_raw, (pd.Timestamp, datetime)):
            competencia = competencia_raw.strftime("%m/%Y")
        else:
            competencia = str(competencia_raw).strip()
            
        comp_path = competencia.replace("/", "")
        return pasta_base, comp_path, competencia
    except Exception as e:
        raise Exception(f"Erro ao ler planilha: {str(e)}")
```

### 📄 `services\logging_service.py`

```python
import logging
from datetime import datetime
from pathlib import Path

# Variável global para controlar se já configuramos o logging
_logging_configured = False

def setup_logging():
    """Configura o sistema de logging apenas para erros"""
    global _logging_configured
    
    if _logging_configured:
        return
    
    # Obtém o diretório raiz do projeto
    project_root = Path(__file__).parent.parent
    
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)
    

    log_filename = f"app_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
    log_path = log_dir / log_filename
    

    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    

    logging.basicConfig(
        level=logging.ERROR,  # Apenas erros
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_path, encoding='utf-8'),
        ]
    )
    
    _logging_configured = True
    return str(log_path)

def log_error(empresa_nome, empresa_codigo, etapa_processo, mensagem_erro, detalhes_adicionais=None):
    """
    Registra um erro no arquivo de log
    """
    # Configura o logging apenas na primeira vez
    log_path = setup_logging()  # noqa: F841
    
    log_message = f"""
╔═══════════════════════════════════════════════════════════════
║ ERRO DETECTADO
╠═══════════════════════════════════════════════════════════════
║ Empresa: {empresa_nome}
║ Código: {empresa_codigo}
║ Etapa: {etapa_processo}
║ Horário: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
╠═══════════════════════════════════════════════════════════════
║ Mensagem de erro:
║   {mensagem_erro}
╠═══════════════════════════════════════════════════════════════
"""

    if detalhes_adicionais:
        log_message += "║ Detalhes adicionais:\n"
        for key, value in detalhes_adicionais.items():
            log_message += f"║   {key}: {value}\n"
    
    log_message += "╚═══════════════════════════════════════════════════════════════\n"
    
    logging.error(log_message)

def log_warning(empresa_nome, empresa_codigo, etapa_processo, mensagem):
    """
    Registra um aviso (apenas no console, não no arquivo)
    """
    warning_message = f"""
╔═══════════════════════════════════════════════════════════════
║ AVISO
╠═══════════════════════════════════════════════════════════════
║ Empresa: {empresa_nome}
║ Código: {empresa_codigo}
║ Etapa: {etapa_processo}
║ Horário: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
╠═══════════════════════════════════════════════════════════════
║ Mensagem:
║   {mensagem}
╚═══════════════════════════════════════════════════════════════\n
"""
    # Usa print para exibir no console sem salvar no arquivo de log
    print(warning_message)

def log_info(empresa_nome, empresa_codigo, etapa_processo, mensagem):
    """
    Registra uma informação (apenas no console, não no arquivo)
    """
    info_message = f"""
╔═══════════════════════════════════════════════════════════════
║ INFORMAÇÃO
╠═══════════════════════════════════════════════════════════════
║ Empresa: {empresa_nome}
║ Código: {empresa_codigo}
║ Etapa: {etapa_processo}
║ Horário: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
╠═══════════════════════════════════════════════════════════════
║ Mensagem:
║   {mensagem}
╚═══════════════════════════════════════════════════════════════\n
"""
    # Usa print para exibir no console sem salvar no arquivo de log
    print(info_message)

# Não inicializa o logging automaticamente agora
# O logging será configurado apenas quando ocorrer o primeiro erro
```

### 📄 `services\nfse_service.py`

```python
from playwright.sync_api import Page
from utils.error_handling import capturar_toast_erro
from utils.file_utils import tentar_download

def nsfe_competencia(page: Page, competencia):
    try:
        page.wait_for_load_state("load", timeout=90000)
        # Garante que os inputs da competência estão visíveis antes de interagir
        page.wait_for_selector('.jarch__filterperiod input[data-p-label="Inicio"]', state="visible")
        
        comp_ini_NFSe = page.locator('.jarch__filterperiod input[data-p-label="Inicio"]')
        print(f"[NFSE] Preenchendo período de competência ({competencia}) para NFSe.")
        for i in range(comp_ini_NFSe.count()):
            input_element = comp_ini_NFSe.nth(i)
            if input_element.is_visible():
                input_element.click()
                input_element.type(competencia)
                break
        page.wait_for_timeout(250)

        comp_fim_NFSe = page.locator('.jarch__filterperiod input[data-p-label="Fim"]')
        for i in range(comp_fim_NFSe.count()):
            input_element = comp_fim_NFSe.nth(i)
            if input_element.is_visible():
                input_element.click()
                input_element.type(competencia)
                break

        # Limpa os campos de Data Início e Data Fim (se existirem e forem diferentes da competência)
        print("[NFSE] Limpando campos de 'Data Inicio' e 'Data Fim' (se aplicável).")
        page.get_by_role("combobox", name="Data Inicio").fill("")
        page.get_by_role("combobox", name="Data Fim").fill("")
    except Exception as e:
        raise Exception(f"[ERRO] Falha ao preencher competência para NFSe: {e}")
        

def nsfe_download(page: Page, current_nome_empresa, ER, pasta_base, comp_path, competencia, current_codigo):
    if ER == "Recebidas":
        try:
            print("\n[NFSE] Iniciando coleta de NFSe - Recebidas...")
            page.locator("label", has_text="Recebidas").click() # Seleciona a opção "Recebidas"
            page.wait_for_timeout(400)
            page.get_by_role("link", name=" Gerar Relação Notas").click() # Clica para gerar a relação de notas
            print("[NAVEGADOR] Clique em Gerar Relação Notas")
            page.wait_for_load_state("load", timeout=30000)
            page.wait_for_timeout(2000)

            # Verifica se há mensagem de erro "Nenhuma nota fiscal" para Recebidas
            erro_Recebidas = capturar_toast_erro(page, current_nome_empresa, competencia, "Tomador", current_codigo, pasta_base, comp_path, Mensagem="Nenhuma nota fiscal")
            if erro_Recebidas:
                print(f"[NFSE] Nenhuma nota fiscal Recebida encontrada para '{current_nome_empresa}' na competência '{competencia}'.")
                # Se não houver notas, recarrega a página para resetar os filtros para a próxima categoria
                print("[NFSE] Recarregando página de exportação de NFSe para próxima etapa.")
                page.goto("https://receita.joaopessoa.pb.gov.br/notafiscal/paginas/exportacaonota/exportacaoNota.jsf", wait_until='load', timeout=30000)
                nsfe_competencia(page, competencia)
            else:
                page.wait_for_load_state('load')
                page.wait_for_timeout(3000)
                erro_Recebidas = capturar_toast_erro(page, current_nome_empresa, competencia, "Tomador", current_codigo, pasta_base, comp_path, Mensagem="Nenhuma nota fiscal")
                if erro_Recebidas:
                    print(f"[2][NFSE] Nenhuma nota fiscal Recebida encontrada para '{current_nome_empresa}' na competência '{competencia}'.")
                    # Se não houver notas, recarrega a página para resetar os filtros para a próxima categoria
                    print("[NFSE] Recarregando página de exportação de NFSe para próxima etapa.")
                    page.goto("https://receita.joaopessoa.pb.gov.br/notafiscal/paginas/exportacaonota/exportacaoNota.jsf", wait_until='load', timeout=30000)
                    nsfe_competencia(page, competencia)
                else:
                    # Se houver notas, tenta fazer o download
                    tentar_download(page, current_nome_empresa, comp_path, "Tomador", pasta_base, current_codigo)
        except Exception as e:
            raise Exception(f"[ERRO] Falha ao coletar NFSe Recebidas: {e}")
    elif ER == "Emitidas":
        print("\n[NFSE] Iniciando coleta de NFSe - Emitidas...")
        page.locator("label", has_text="Emitidas").click() # Seleciona a opção "Emitidas"
        page.wait_for_timeout(500)
        page.get_by_role("link", name=" Gerar Relação Notas").click() # Clica para gerar a relação de notas
        page.wait_for_load_state("load", timeout=30000)
        page.wait_for_timeout(3000)
        # Verifica se há mensagem de erro "Nenhuma nota fiscal" para Emitidas
        erro_Emitidas = capturar_toast_erro(page, current_nome_empresa, competencia, "Prestador", current_codigo, pasta_base, comp_path, Mensagem="Nenhuma nota fiscal")
        if erro_Emitidas:
            print(f"[NFSE] Nenhuma nota fiscal Emitida encontrada para '{current_nome_empresa}' na competência '{competencia}'.")
        else:
            page.wait_for_load_state('load')
            page.wait_for_timeout(3000)
            erro_Emitidas = capturar_toast_erro(page, current_nome_empresa, competencia, "Prestador", current_codigo, pasta_base, comp_path, Mensagem="Nenhuma nota fiscal")
            if erro_Emitidas:
                print(f"[2][NFSE] Nenhuma nota fiscal Emitida encontrada para '{current_nome_empresa}' na competência '{competencia}'.")
            else:
                # Se houver notas, tenta fazer o download
                tentar_download(page, current_nome_empresa, comp_path, "Prestador", pasta_base, current_codigo)
```

### 📄 `services\retroactive_service.py`

```python
from playwright.sync_api import Page
from datetime import datetime
import calendar
from pathlib import Path
from utils.file_utils import limpar_arquivos_de_erro

def get_previous_month_date(date_obj, months_back):
    """Calcula uma data subtraindo meses."""
    year = date_obj.year
    month = date_obj.month
    
    total_months = (year * 12 + month) - 1 - months_back
    new_year = total_months // 12
    new_month = (total_months % 12) + 1
    
    return date_obj.replace(year=new_year, month=new_month)

def calcular_datas_retroativas(competencia_str):
    """
    Calcula as datas de Emissão (Competência Atual) e Competência (6 meses atrás).
    Entrada: "MM/AAAA"
    """
    dt_comp = datetime.strptime(competencia_str, "%m/%Y")

    # 1. Datas de Emissão (Baseado na competência selecionada)
    # Início: 01/MM/AAAA
    emissao_ini = dt_comp.replace(day=1).strftime("%d/%m/%Y")
    # Fim: Último dia do mês
    last_day = calendar.monthrange(dt_comp.year, dt_comp.month)[1]
    emissao_fim = dt_comp.replace(day=last_day).strftime("%d/%m/%Y")

    # 2. Datas de Competência (Retroativo 6 meses)
    # Início: 6 meses antes
    dt_start_retro = get_previous_month_date(dt_comp, 6)
    comp_ini = dt_start_retro.strftime("%m/%Y")

    # Fim: 1 mês antes
    dt_end_retro = get_previous_month_date(dt_comp, 1)
    comp_fim = dt_end_retro.strftime("%m/%Y")

    return emissao_ini, emissao_fim, comp_ini, comp_fim

def consulta_retroativa(page: Page, competencia, pasta_base, current_codigo, current_nome_empresa, comp_path):
    try:
        print(f"\n[RETROATIVA] ⏳ Iniciando Consulta Retroativa para '{current_nome_empresa}'...")
        
        # Calcular datas
        emissao_ini, emissao_fim, comp_ini, comp_fim = calcular_datas_retroativas(competencia)
        print(f"[RETROATIVA] Filtros - Emissão: {emissao_ini} a {emissao_fim} | Competência: {comp_ini} a {comp_fim}")

        # Navegação
        # Garante que o menu Gerenciar NFSe está expandido ou clica nele
        try:
            page.get_by_role("link", name="Gerenciar NFSe ").click(timeout=2000)
        except Exception:
            # Pode já estar aberto
            pass
        
        # Clica em Consulta Nota Fiscal
        # Usando filtro de texto para ser mais robusto que ID
        locators = page.locator("a").filter(has_text="Consulta Nota Fiscal")
        # Itera para encontrar o elemento visível, pois a página pode ter elementos duplicados.
        for i in range(locators.count()):
            element = locators.nth(i)
            if element.is_visible():
                element.click()
                break
        page.wait_for_load_state("load")

        # Preencher Emissão (Competência Atual)
        # Data Inicio Emissão
        page.locator("input[name$='idStart_input']").first.click()
        page.locator("input[name$='idStart_input']").first.fill(emissao_ini)
        page.keyboard.press("Tab") # Fecha calendário se abrir

        # Data Fim Emissão
        page.locator("input[name$='idEnd_input']").first.click()
        page.locator("input[name$='idEnd_input']").first.fill(emissao_fim)
        page.keyboard.press("Tab")

        # Preencher Competência (Retroativa)
        # O campo de competência geralmente é o segundo conjunto de inputs ou rotulado especificamente
        # Baseado no fluxo padrão, vamos buscar pelo label ou placeholder se possível, 
        # mas assumindo a ordem do formulário conforme descrição:
        
        # Competencia Inicial
        page.locator("input[name$='idStart_input']").nth(1).click()
        page.locator("input[name$='idStart_input']").nth(1).fill(comp_ini)
        page.keyboard.press("Tab")

        # Competencia Final
        page.locator("input[name$='idEnd_input']").nth(1).click()
        page.locator("input[name$='idEnd_input']").nth(1).fill(comp_fim)
        page.keyboard.press("Tab")

        # Pesquisar
        page.get_by_role("link", name=" Pesquisar").click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1500)

        # Verificação de Resultados
        # Verifica se a mensagem de "Nenhum registro" está visível
        msg_nenhum_registro = "Nenhum registro foi encontrado"
        if page.get_by_text(msg_nenhum_registro).is_visible():
            print("[RETROATIVA] ℹ️ Nenhum registro retroativo encontrado para o período.")
            return

        # Se chegou aqui, existem registros. Iniciar Download.
        print("[RETROATIVA] Registros encontrados. Iniciando exportação PDF...")

        # 1. Clicar em Imprimir
        page.get_by_role("button", name=" Imprimir").click()
        
        # 2. Clicar na opção PDF (Menu)
        page.get_by_role("link", name="PDF", exact=True).click()
        
        # 3. Clicar no PDF Download (Modal/Confirmação)
        # Usando expect_download para capturar o evento
        with page.expect_download(timeout=30000) as download_info:
            # O seletor exato pode variar, mas geralmente tem o ícone de download
            page.get_by_role("link", name="PDF ").click()
        
        download = download_info.value
        
        # Definir caminho de salvamento
        # Estrutura: Pasta Base / Consulta Retroativa / Codigo-Nome / Competencia / Arquivo
        nome_arquivo = f"Consulta_Retroativa_{current_codigo}-{current_nome_empresa}.pdf"
        caminho_final = Path(f"{pasta_base}/Consulta Retroativa/{current_codigo}-{current_nome_empresa}/{comp_path}/{nome_arquivo}")
        
        caminho_final.parent.mkdir(parents=True, exist_ok=True)
        
        download.save_as(caminho_final)
        print(f"[RETROATIVA] ✅ PDF salvo com sucesso em: {caminho_final}")
        
        # Limpa arquivos de erro antigos da pasta, já que o download foi bem-sucedido
        limpar_arquivos_de_erro(caminho_final.parent)
        
        # Fechar janelas/modais se necessário (opcional, dependendo do comportamento da página)
        page.keyboard.press("Escape")

    except Exception as e:
        print(f"[ERRO] Falha na Consulta Retroativa: {e}")
        # Não lançamos erro crítico para não parar o fluxo principal, apenas logamos
        pass
```

### 📄 `services\selection_service.py`

```python
from playwright.sync_api import Page

def garantir_contexto(page: Page):
    page.goto("https://receita.joaopessoa.pb.gov.br/notafiscal/paginas/selecionacadastro/selecionaCadastro.jsf", wait_until="networkidle")
    page.wait_for_timeout(500)

def selecionar_empresa(page: Page, current_codigo: str, current_nome_empresa: str, current_cnpj_cpf: str):
    try:
        print(f"[SELECAO] Preenchendo CNPJ/CPF: {current_cnpj_cpf} e pesquisando...")
        page.get_by_role("textbox", name="CPF/CNPJ").click()
        page.get_by_role("textbox", name="CPF/CNPJ").fill(current_cnpj_cpf)
        page.get_by_role("link", name=" Pesquisar").click()
        page.wait_for_timeout(2500)
        print(f"[SELECAO] Selecionando empresa '{current_nome_empresa}'.")
        page.get_by_role("link", name="").click(timeout=5000)
        page.wait_for_url("https://receita.joaopessoa.pb.gov.br/notafiscal/paginas/login/bemVindo.jsf", wait_until="load", timeout=60000)
        page.wait_for_timeout(1000)
        print("[SELECAO] Empresa selecionada com sucesso.")
        return True
    except Exception as e:
        try:
            if page.locator("text=Nenhum registro encontrado").is_visible(timeout=5000):
                # Retorna False em vez de levantar exceção
                return False
        except Exception:
            pass
        raise Exception(f"[SELECAO] Erro ao selecionar empresa '{current_nome_empresa}': {e}")

```

### 📄 `services\__init__.py`

```python

```

### 📄 `utils\error_handling.py`

```python
from pathlib import Path
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError


def capturar_toast_erro(page: Page, current_nome_empresa, competencia, Prest_Tom,current_codigo, pasta_base, comp_path, Mensagem="Nenhum registro encontrado"):
    """
    Captura e salva um screenshot de um toast de erro na tela, se presente.
    Cria a estrutura de pastas e salva a imagem do erro.
    """
    try:
        # Aguarda pelo toast de erro com a mensagem específica por até 2 segundos
        toast = page.locator("div.toast-message", has_text=Mensagem).first
        toast.wait_for(timeout=2000) # Pequeno timeout para não aguardar muito

        # Define o local de salvamento baseado no tipo de erro
        if Mensagem in ["Nenhum registro encontrado", "Nenhuma nota fiscal"]:
            pasta_erro = Path(f"{pasta_base}/{Prest_Tom}/{current_codigo}-{current_nome_empresa}/{comp_path}")
        else:
            pasta_erro = Path("Print Logs")
        
        pasta_erro.mkdir(parents=True, exist_ok=True) # Garante que o diretório exista

        # Define o caminho final da imagem do erro
        caminho_imagem_erro = pasta_erro / f"ERRO_{Mensagem.replace(' ', '_')}_{current_nome_empresa}.jpg"

        # Salva um print da tela inteira quando o toast de erro está visível
        page.screenshot(path=str(caminho_imagem_erro))
        print(f"[INFO] Mensagem '{Mensagem}' capturado para {current_nome_empresa} ({Prest_Tom}). Screenshot salvo em: {caminho_imagem_erro}")
        return True  # Indica que um erro foi capturado
    except PlaywrightTimeoutError:
        # O toast de erro não foi encontrado no tempo limite
        print(f"[INFO] Nenhum toast de erro '{Mensagem}' detectado para {current_nome_empresa} ({Prest_Tom}).")
        return False # Indica que nenhum erro foi capturado
    

def registrar_erro(erros_por_empresa, codigo, nome, etapa, erro_msg):
    if codigo not in erros_por_empresa:
        erros_por_empresa[codigo] = {
            "nome": nome,
            "erros": []
        }
    erros_por_empresa[codigo]["erros"].append({
        "etapa": etapa,
        "mensagem": str(erro_msg)
    })
```

### 📄 `utils\file_utils.py`

```python
import re
from pathlib import Path
import os


def limpar_nome(nome: str) -> str:
    """Remove caracteres inválidos do nome do arquivo."""
    nome_limpo = re.sub(r'[<>:"/\\|?*]', '', nome)
    return nome_limpo.strip()

def limpar_arquivos_de_erro(diretorio: Path):
    """
    Verifica um diretório e remove arquivos de screenshot de erro (`ERRO_*.jpg`).
    """
    if not diretorio.is_dir():
        return

    try:
        for item in diretorio.iterdir():
            # O erro é salvo como .jpg pela função capturar_toast_erro
            if item.is_file() and item.name.startswith("ERRO_") and item.name.endswith(".jpg"):
                print(f"[LIMPEZA] 🧹 Removendo arquivo de erro antigo: {item.name}")
                os.remove(item)
    except Exception as e:
        print(f"[LIMPEZA] ⚠️ Falha ao tentar limpar arquivos de erro em {diretorio}: {e}")

def tentar_download(page, current_nome_empresa, competencia, tipo, pasta_base, current_codigo):
    """
    Tenta realizar o download de arquivos (XML/PDF) com múltiplas tentativas.
    Cria a estrutura de pastas necessária e trata falhas de download.
    """
    competencia_sem_barra = competencia.replace('/', '')  # noqa: F841
    if tipo == "Tomador":
        filename = f"XML_Recebidas-{current_codigo}-{current_nome_empresa}.xml"
        caminho = Path(f"{pasta_base}/Tomador/{current_codigo}-{current_nome_empresa}/{competencia}/{filename}")
    elif tipo == "Prestador":
        filename = f"XML_Emitidas-{current_codigo}-{current_nome_empresa}.xml"
        caminho = Path(f"{pasta_base}/Prestador/{current_codigo}-{current_nome_empresa}/{competencia}/{filename}")
    else:
        caminho = Path(f"{pasta_base}/{tipo}/{current_codigo}-{current_nome_empresa}/{competencia}/{current_codigo}-{current_nome_empresa}.pdf")

    tentativas = 0
    max_tentativas = 3

    while tentativas < max_tentativas:
        try:
            print(f"[DOWNLOAD] Tentativa {tentativas + 1}/{max_tentativas} de download '{tipo}' para {current_nome_empresa}...")
            
            # Aguarda o download ser iniciado por até 25 segundos0
            with page.expect_download(timeout=25000) as download_info:
                page.wait_for_timeout(200) # Pequena pausa para garantir que o clique seja processado
                page.get_by_role("link", name=" Download").click() # Clica no botão de download
            
            download = download_info.value
            
            # Garante que o diretório de destino exista antes de salvar
            caminho.parent.mkdir(parents=True, exist_ok=True)
            download.save_as(str(caminho)) # Salva o arquivo no caminho especificado
            print(f"[DOWNLOAD] ✅ Download de '{tipo}' concluído com sucesso para {current_nome_empresa}. Salvo em: {caminho}")
            
            # Limpa arquivos de erro antigos da pasta, já que o download foi bem-sucedido
            limpar_arquivos_de_erro(caminho.parent)
            return True
        except Exception as e:
            print(f"[DOWNLOAD] ⚠️ Tentativa {tentativas + 1} falhou para '{tipo}' de {current_nome_empresa}: {e}")
            tentativas += 1
            # Tenta restaurar a interface para uma nova tentativa
            try:
                if tipo in ["Tomador", "Prestador"]:
                    label_text = "Recebidas" if tipo == "Tomador" else "Emitidas"
                    page.locator("label", has_text=label_text).click()
                    page.wait_for_timeout(400)
                    page.get_by_role("link", name=" Gerar Relação Notas").click()
                    page.wait_for_timeout(800)
            except Exception as click_error:
                print(f"[DOWNLOAD] ❌ Falha ao tentar restaurar interface após erro para '{tipo}' de {current_nome_empresa}: {click_error}")
                break # Sai do loop de tentativas se a interface não puder ser restaurada
    
    print(f"[DOWNLOAD] ❌ Falha total no download de '{tipo}' para a empresa: {current_nome_empresa}. Todas as {max_tentativas} tentativas esgotadas.")
    try:
        close_button_locator = page.get_by_role("button", name="Fechar")
        if close_button_locator.is_visible():
            print("Botão 'X' para fechar pop-up visível. Clicando...")
            close_button_locator.click()
            print("Pop-up fechado.")
    except Exception as e:  # noqa: F841
        pass
    # Cria um arquivo de log de erro na pasta de destino
    erro_path_dir = caminho.parent
    erro_path_dir.mkdir(parents=True, exist_ok=True) # Garante que o diretório de erro exista
    
    # --- CORREÇÃO: Salvar Screenshot do erro ---
    try:
        print_logs_dir = Path("Print Logs")
        print_logs_dir.mkdir(exist_ok=True)
        screenshot_path = print_logs_dir / f"ERRO_Download_{tipo.replace('/', '_')}_{current_nome_empresa}.jpg"
        page.screenshot(path=str(screenshot_path))
        print(f"[DOWNLOAD] 📸 Screenshot de erro salvo em: {screenshot_path}")
    except Exception as screen_err:
        print(f"[DOWNLOAD] ⚠️ Falha ao salvar screenshot de erro: {screen_err}")
    # -------------------------------------------

    with open(erro_path_dir / f"Falha_Download_{tipo.replace('/', '_')}.txt", "w", encoding="utf-8") as f:
        f.write(f"Falha ao salvar '{tipo}' da empresa {current_nome_empresa} na competência {competencia}. Verifique a conexão ou o portal.\n")
    return False
```

### 📄 `utils\menu_utils.py`

```python
from playwright.sync_api import Page
from pathlib import Path

def gerenciar_nfse(page: Page, i):
    if i == 0:
        print("[NAVEGADOR] Clicando em 'Gerenciar NFSe' no menu principal.")
        page.get_by_role("link", name="Gerenciar NFSe ").click()
        page.wait_for_timeout(1000) # Pequena pausa para garantir o carregamento

def livrofiscal_menu(page: Page):
    print("[NAVEGADOR] Clicando em 'Livro Fiscal' no menu de navegação.")
    locators = page.locator('span.nav-label', has_text="Livro Fiscal")
    print("[LOG] Clicando em Livro Fiscal")
    count = locators.count()
    for i in range(count):
        element = locators.nth(i)
        if element.is_visible():
            element.click()
            break
    page.wait_for_timeout(1000) # Pequena pausa para garantir o carregamento
    page.wait_for_load_state('load', timeout=60000)


def nfse_menu(page: Page, company_name: str = "Empresa_Desconhecida"):
    try:
        print("\n[NFSE] Iniciando coleta de NFSe's (Recebidas/Emitidas)...")
        print("[NAVEGADOR] Navegando para a seção de 'Exportar NFSe'.")
        # Usando seletor baseado no texto visível e classe, iterando para evitar erro de duplicidade
        locators = page.locator('span.nav-label', has_text="Exportar NFSe")
        clicked = False
        for i in range(locators.count()):
            element = locators.nth(i)
            if element.is_visible():
                element.click()
                clicked = True
                break
        if not clicked and locators.count() > 0:
            locators.first.click() # Fallback
            
        page.wait_for_load_state('load') # Aguarda o carregamento da página
        page.wait_for_timeout(400)
    except Exception as e:
        try:
            # Tenta salvar um print do erro para análise
            log_dir = Path("Print Logs")
            log_dir.mkdir(exist_ok=True)
            screenshot_path = log_dir / f"ERRO_Navegacao_NFSe_{company_name}.jpg"
            page.screenshot(path=str(screenshot_path))
            print(f"[ERRO] 📸 Screenshot da falha de navegação salvo em: {screenshot_path}")
        except Exception:
            pass
        raise Exception(f"[ERRO] Falha ao navegar para a seção de 'Exportação de NFSe'. Detalhes: {e}")
```

### 📄 `utils\playwright_utils.py`

```python
from config.settings import HEADLESS, SLOW_MO, SCREEN_SIZE
import subprocess
import sys

def inicializar_playwright(p):
    print("[NAVEGADOR] Iniciando navegador...")
    browser = p.firefox.launch(
        headless=HEADLESS,
        args=["--start-maximized", "--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
        slow_mo=SLOW_MO
    )
    page = browser.new_page()
    page.set_viewport_size(SCREEN_SIZE)

    # --- OTIMIZAÇÃO DE PERFORMANCE ---
    # Intercepta e cancela o carregamento de recursos desnecessários
    def route_handler(route):
        # Bloqueia imagens, fontes e mídias
        if route.request.resource_type in ["image", "media", "font"]:
            route.abort()
        else:
            route.continue_()

    # Aplica o filtro em todas as requisições
    page.route("**/*", route_handler)
    
    return page



def install_playwright_browsers():
    """
    Verifica e instala os navegadores da Playwright usando o CLI.
    """
    print("[SETUP] Verificando e instalando navegadores Playwright (se necessário)...")
    try:
        if getattr(sys, 'frozen', False):
            command = [sys.executable, '-m', 'playwright', 'install']
        else:
            command = ['playwright', 'install']
            
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        print("[SETUP] Instalação dos navegadores Playwright concluída com sucesso!")
    except subprocess.CalledProcessError as e:
        print(f"[ERRO] Falha ao instalar os navegadores Playwright. Código de saída: {e.returncode}")
        print(f"[ERRO] Saída de erro:\n{e.stderr}")
        sys.exit(1)
    except FileNotFoundError:
        print("[ERRO] Comando 'playwright' não encontrado.")
        print("[ERRO] Certifique-se de que a Playwright esteja instalada e acessível no PATH.")
        sys.exit(1)
```

### 📄 `utils\__init__.py`

```python

```
