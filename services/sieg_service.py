"""
Serviço de upload para o SIEG (cofre fiscal eletrônico).

Adaptado de SIEG_API.py da automação antiga. A lógica principal de upload,
retry e manifesto SHA256 é mantida. Mudança: os XMLs agora vêm do webservice
(salvos em disco pelo file_utils.py) em vez de serem baixados pelo browser.

O manifesto evita reenvio de arquivos já processados em execuções anteriores.
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

from config.settings import SIEG_API_KEY, SIEG_UPLOAD_URL
from services.logging_service import log_error, log_info, log_warning


# ── Upload de um arquivo ──────────────────────────────────────────────────────


def upload_xml_file(
    api_key: str,
    xml_path: Path,
    *,
    timeout: int = 60,
    double_encode_api_key: bool = False,
) -> dict[str, Any]:
    """
    Faz upload de um único arquivo XML para o SIEG.

    Args:
        api_key: Chave de API do SIEG
        xml_path: Caminho para o arquivo XML
        timeout: Timeout HTTP em segundos
        double_encode_api_key: Se True, aplica URL-encode duplo na key

    Returns:
        Dict com: ok (bool), status_code (int), error (str|None)
    """
    encoded_key = _encode_api_key(api_key, double_encode=double_encode_api_key)
    url = f"{SIEG_UPLOAD_URL}?api_key={encoded_key}"

    xml_bytes = xml_path.read_bytes()
    xml_b64 = base64.b64encode(xml_bytes).decode("ascii")

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
    }
    payload = {"Xml": xml_b64}

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
    except requests.RequestException as exc:
        return {"ok": False, "status_code": 0, "error": f"Rede/timeout: {exc}"}

    ok = 200 <= resp.status_code < 300
    error = None
    if not ok:
        try:
            j = resp.json()
            error = j.get("message") or j.get("Message") or j.get("error")
        except Exception:
            pass
        error = error or f"HTTP {resp.status_code}"

    return {"ok": ok, "status_code": resp.status_code, "error": error}


# ── Batch upload pós-processamento ────────────────────────────────────────────


def upload_all_nfse(
    api_key: str,
    pasta_base: str | Path,
    *,
    timeout: int = 60,
    double_encode_api_key: bool = False,
    retries: int = 3,
    retry_backoff_sec: float = 2.0,
    manifest_filename: str = ".sieg_upload_manifest.json",
    fail_fast: bool = False,
) -> dict[str, Any]:
    """
    Faz upload em lote de todas as NFS-e salvas em disco para o SIEG.
    Usa manifesto SHA256 para evitar reenvio de arquivos já processados.

    Padrões de busca:
      - Prestador/**/XML_Emitidas-*.xml
      - Tomador/**/XML_Recebidas-*.xml
      - Consulta Retroativa/**/XML_*.xml

    Args:
        api_key: Chave de API do SIEG
        pasta_base: Pasta raiz de saída (mesma do settings.OUTPUT_BASE_PATH)
        timeout: Timeout HTTP por arquivo
        double_encode_api_key: Aplicar URL-encode duplo na key
        retries: Número de tentativas por arquivo
        retry_backoff_sec: Base do backoff exponencial (segundos)
        manifest_filename: Nome do arquivo de manifesto
        fail_fast: Se True, para ao primeiro erro

    Returns:
        Dict com: total_found, skipped, sent_ok, sent_fail, fails
    """
    base = Path(pasta_base)
    manifest_path = base / manifest_filename
    manifest = _load_manifest(manifest_path)
    already_sent: dict[str, dict] = manifest.get("sent", {})

    xmls = _find_nfse_xmls(base)

    summary: dict[str, Any] = {
        "total_found": len(xmls),
        "skipped": 0,
        "sent_ok": 0,
        "sent_fail": 0,
        "fails": [],
    }

    for xml_path in xmls:
        try:
            digest = _sha256_file(xml_path)
        except Exception as exc:
            summary["sent_fail"] += 1
            summary["fails"].append({"file": str(xml_path), "error": str(exc)})
            if fail_fast:
                break
            continue

        if digest in already_sent:
            summary["skipped"] += 1
            continue

        result = None
        for attempt in range(1, retries + 1):
            result = upload_xml_file(
                api_key=api_key,
                xml_path=xml_path,
                timeout=timeout,
                double_encode_api_key=double_encode_api_key,
            )
            if result["ok"]:
                break
            sc = result.get("status_code", 0)
            if sc == 0 or 500 <= sc <= 599:
                time.sleep(retry_backoff_sec * attempt)
                continue
            break  # Erro 4xx — não adianta tentar de novo

        if result and result["ok"]:
            summary["sent_ok"] += 1
            already_sent[digest] = {
                "file": str(xml_path),
                "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                "status_code": result.get("status_code"),
            }
            # Salvar manifesto a cada 10 uploads bem-sucedidos
            if summary["sent_ok"] % 10 == 0:
                _save_manifest(manifest_path, {"sent": already_sent})
            log_info("SIEG", "N/A", "Upload", f"OK | HTTP {result.get('status_code')} | {xml_path.name}")
        else:
            err = result.get("error", "desconhecido") if result else "sem resposta"
            summary["sent_fail"] += 1
            summary["fails"].append({"file": str(xml_path), "error": err})
            log_warning("SIEG", "N/A", "Upload", f"ERRO | {xml_path.name} | {err}")
            if fail_fast:
                break

    _save_manifest(manifest_path, {"sent": already_sent})
    return summary


# ── Helpers ────────────────────────────────────────────────────────────────────


def _find_nfse_xmls(base: Path) -> list[Path]:
    """Localiza todos os XMLs de NFS-e (competência + retroativo)."""
    patterns = [
        "Prestador/**/XML_Emitidas-*.xml",
        "Tomador/**/XML_Recebidas-*.xml",
        "Consulta Retroativa/**/XML_*.xml",
    ]
    files: list[Path] = []
    for pat in patterns:
        files.extend(base.glob(pat))
    return sorted(set(files))


def _encode_api_key(api_key: str, double_encode: bool = False) -> str:
    api_key = (api_key or "").strip()
    if not api_key:
        raise ValueError("SIEG_API_KEY vazia.")
    once = quote(api_key, safe="")
    return quote(once, safe="") if double_encode else once


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_manifest(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"sent": {}}


def _save_manifest(path: Path, manifest: dict):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        log_error("SIEG", "N/A", "Manifesto", f"Falha ao salvar manifesto: {exc}")
