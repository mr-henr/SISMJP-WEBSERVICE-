"""
Serviço de integração com o NIBO (sistema contábil).

Adaptado de NIBO-Conferencia.py da automação antiga. Faz upload dos arquivos
gerados (XMLs de NFS-e e Excel do Livro Fiscal) para o NIBO e os envia para
o processo de conferência.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import requests

from config.settings import (
    NIBO_ACCOUNTING_FIRM_ID,
    NIBO_API_KEY,
    NIBO_BASE_URL,
    NIBO_USER_ID,
)
from services.logging_service import log_error, log_info, log_warning


def upload_arquivo_nibo(filepath: Path) -> str | None:
    """
    Faz upload de um arquivo (XML ou XLSX) para o NIBO.

    Args:
        filepath: Caminho do arquivo a enviar

    Returns:
        ID do arquivo no NIBO, ou None em caso de falha
    """
    url = f"{NIBO_BASE_URL}/accountingfirms/{NIBO_ACCOUNTING_FIRM_ID}/files"
    headers = {
        "X-API-Key": NIBO_API_KEY,
        "X-User-Id": NIBO_USER_ID,
    }

    try:
        with filepath.open("rb") as f:
            resp = requests.post(
                url,
                headers=headers,
                files={"file": (filepath.name, f)},
                timeout=60,
            )
        resp.raise_for_status()
        file_id = resp.json().get("id")
        log_info("NIBO", "N/A", "Upload", f"OK | {filepath.name} → id={file_id}")
        return file_id
    except requests.HTTPError as exc:
        log_error("NIBO", "N/A", "Upload", f"HTTP {exc.response.status_code} | {filepath.name}: {exc}")
    except Exception as exc:
        log_error("NIBO", "N/A", "Upload", f"Erro | {filepath.name}: {exc}")
    return None


def enviar_conferencia(file_id: str, filename: str) -> bool:
    """
    Envia um arquivo já carregado para o fluxo de conferência do NIBO.

    Args:
        file_id: ID retornado pelo upload_arquivo_nibo
        filename: Nome do arquivo (para logs)

    Returns:
        True se enviado com sucesso
    """
    url = f"{NIBO_BASE_URL}/accountingfirms/{NIBO_ACCOUNTING_FIRM_ID}/conferences"
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": NIBO_API_KEY,
        "X-User-Id": NIBO_USER_ID,
    }

    try:
        resp = requests.post(url, json={"fileId": file_id}, headers=headers, timeout=60)
        resp.raise_for_status()
        log_info("NIBO", "N/A", "Conferência", f"Enviado para conferência: {filename}")
        return True
    except requests.HTTPError as exc:
        log_error("NIBO", "N/A", "Conferência",
                  f"HTTP {exc.response.status_code} | {filename}: {exc}")
    except Exception as exc:
        log_error("NIBO", "N/A", "Conferência", f"Erro | {filename}: {exc}")
    return False


def upload_tudo_para_nibo(pasta_base: str | Path) -> dict[str, Any]:
    """
    Faz upload de todos os XMLs e Livros Fiscais (XLSX) gerados para o NIBO
    e os envia para conferência.

    Padrões de busca:
      - Prestador/**/*.xml  → notas emitidas
      - Tomador/**/*.xml    → notas recebidas
      - Prestador/**/*.xlsx → livros fiscais prestador
      - Tomador/**/*.xlsx   → livros fiscais tomador

    Args:
        pasta_base: Pasta raiz de saída

    Returns:
        Dict com: ok (int), fail (int)
    """
    if not NIBO_API_KEY or not NIBO_ACCOUNTING_FIRM_ID:
        log_warning(
            "NIBO", "N/A", "Upload",
            "Credenciais NIBO não configuradas (NIBO_API_KEY / NIBO_ACCOUNTING_FIRM_ID). "
            "Upload ignorado.",
        )
        return {"ok": 0, "fail": 0}

    base = Path(pasta_base)
    patterns = [
        "Prestador/**/*.xml",
        "Tomador/**/*.xml",
        "Consulta Retroativa/**/*.xml",
        "Prestador/**/*.xlsx",
        "Tomador/**/*.xlsx",
    ]

    arquivos: list[Path] = []
    for pat in patterns:
        arquivos.extend(base.glob(pat))
    arquivos = sorted(set(arquivos))

    summary = {"ok": 0, "fail": 0}

    for filepath in arquivos:
        file_id = upload_arquivo_nibo(filepath)
        if file_id:
            if enviar_conferencia(file_id, filepath.name):
                summary["ok"] += 1
            else:
                summary["fail"] += 1
        else:
            summary["fail"] += 1

    return summary
