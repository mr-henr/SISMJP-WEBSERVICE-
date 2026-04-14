"""
Utilitário simples de retry com backoff exponencial para chamadas SOAP.

Sem dependências externas (não usa tenacity) — mantém o requirements enxuto.
Retenta apenas em falhas *transitórias* de rede/servidor. Erros de negócio
(zeep.exceptions.Fault, NfseServiceError) não são retentados.
"""

from __future__ import annotations

import functools
import socket
import time
from typing import Callable, Iterable, Tuple, Type

import requests

# Exceções consideradas transitórias (vale a pena tentar de novo)
TRANSIENT_EXCEPTIONS: Tuple[Type[BaseException], ...] = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
    socket.timeout,
    ConnectionResetError,
    ConnectionAbortedError,
)


def with_retries(
    max_attempts: int = 3,
    initial_backoff: float = 2.0,
    backoff_factor: float = 2.0,
    retry_on: Iterable[Type[BaseException]] = TRANSIENT_EXCEPTIONS,
    on_retry: Callable[[int, BaseException, float], None] | None = None,
):
    """
    Decorator que retenta a função em caso de erro transitório.

    Args:
        max_attempts: Número total de tentativas (inclui a primeira).
        initial_backoff: Segundos antes da 2ª tentativa (dobra a cada retry).
        backoff_factor: Multiplicador do backoff entre tentativas.
        retry_on: Tupla de exceções que disparam retry.
        on_retry: Callback (tentativa, excecao, proximo_backoff) — para logs.

    Exemplo:
        @with_retries(max_attempts=3, initial_backoff=2.0)
        def consultar_servidor():
            return client.service.Consultar(...)
    """
    retry_on = tuple(retry_on)

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            backoff = initial_backoff
            ultimo_erro: BaseException | None = None
            for tentativa in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except retry_on as exc:
                    ultimo_erro = exc
                    if tentativa >= max_attempts:
                        break
                    if on_retry:
                        try:
                            on_retry(tentativa, exc, backoff)
                        except Exception:
                            pass
                    time.sleep(backoff)
                    backoff *= backoff_factor
            assert ultimo_erro is not None
            raise ultimo_erro
        return wrapper
    return decorator
