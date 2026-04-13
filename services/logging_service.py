"""
Serviço de logging estruturado.

Adaptado do logging_service.py da automação antiga. Mantém a mesma interface
(log_error, log_warning, log_info) para compatibilidade com todos os outros
módulos, mas remove dependências do Playwright.

Os logs são escritos no console (stdout) e opcionalmente em arquivo.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

# Caminho do arquivo de log (None = só console)
_LOG_FILE: Path | None = None


def configurar_log_file(caminho: str | Path):
    """
    Configura escrita de log em arquivo além do console.
    Chame antes de iniciar o processamento, se desejar log persistente.
    """
    global _LOG_FILE
    _LOG_FILE = Path(caminho)
    _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)


def log_error(
    empresa: str,
    codigo: str,
    contexto: str,
    mensagem: str,
    dados_extras: dict | None = None,
):
    """
    Registra um erro (nível ERROR).

    Args:
        empresa: Nome da empresa em processamento
        codigo: Código/IM da empresa
        contexto: Módulo ou operação onde ocorreu o erro
        mensagem: Descrição do erro
        dados_extras: Dados adicionais opcionais para diagnóstico
    """
    _registrar("ERROR", empresa, codigo, contexto, mensagem, dados_extras)


def log_warning(
    empresa: str,
    codigo: str,
    contexto: str,
    mensagem: str,
    dados_extras: dict | None = None,
):
    """Registra um aviso (nível WARNING)."""
    _registrar("WARNING", empresa, codigo, contexto, mensagem, dados_extras)


def log_info(
    empresa: str,
    codigo: str,
    contexto: str,
    mensagem: str,
    dados_extras: dict | None = None,
):
    """Registra uma informação (nível INFO)."""
    _registrar("INFO", empresa, codigo, contexto, mensagem, dados_extras)


def _registrar(
    nivel: str,
    empresa: str,
    codigo: str,
    contexto: str,
    mensagem: str,
    dados_extras: dict | None,
):
    """Formata e escreve a entrada de log."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linha = f"[{ts}] [{nivel}] [{codigo}] [{empresa}] [{contexto}] {mensagem}"

    if dados_extras:
        extras = " | ".join(f"{k}={v}" for k, v in dados_extras.items())
        linha += f" | {extras}"

    # Console
    if nivel == "ERROR":
        print(linha, file=sys.stderr, flush=True)
    else:
        print(linha, flush=True)

    # Arquivo (opcional)
    if _LOG_FILE is not None:
        try:
            with _LOG_FILE.open("a", encoding="utf-8") as f:
                f.write(linha + "\n")
        except OSError:
            pass
