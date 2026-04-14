"""
Serviço de consulta de NFS-e via webservice SISMJP (ABRASF 2.03).

Substitui o antigo nfse_service.py (Playwright) e retroactive_service.py.
Implementa paginação automática para consultas que retornam múltiplas páginas.
"""

from __future__ import annotations

from datetime import datetime

from zeep.exceptions import Fault

from config.settings import RETROACTIVE_MONTHS
from models.nfse_model import NfseData
from services.logging_service import log_error, log_info, log_warning
from services.webservice_client import get_client
from utils.retry_utils import with_retries
from utils.xml_utils import (
    build_consultar_faixa_dict,
    build_consultar_prestado_dict,
    build_consultar_tomado_dict,
    parse_nfse_list_response,
)

# Códigos ABRASF que indicam "nenhum registro encontrado" (não é erro real)
_CODIGOS_SEM_REGISTRO = {"E10", "E4", "E15", "E56"}


def _log_retry(empresa_nome: str, empresa_codigo: str, operacao: str):
    """Retorna um callback on_retry que loga warning antes de cada nova tentativa."""
    def _cb(tentativa: int, exc: BaseException, backoff: float) -> None:
        log_warning(
            empresa_nome,
            empresa_codigo,
            f"{operacao} (retry)",
            f"Tentativa {tentativa} falhou ({type(exc).__name__}: {exc}). "
            f"Nova tentativa em {backoff:.1f}s.",
        )
    return _cb


def _chamar_soap_com_retry(operacao_nome: str, empresa_nome: str, empresa_codigo: str, fn):
    """
    Envolve uma chamada SOAP com retry (3 tentativas, backoff 2s → 4s).
    Só retenta em falhas de rede; SOAP Faults e erros de negócio sobem direto.
    """
    return with_retries(
        max_attempts=3,
        initial_backoff=2.0,
        backoff_factor=2.0,
        on_retry=_log_retry(empresa_nome, empresa_codigo, operacao_nome),
    )(fn)()


class NfseServiceError(Exception):
    """Levantado quando o webservice retorna erros de negócio inesperados."""

    def __init__(self, erros: list[str]):
        self.erros = erros
        super().__init__("; ".join(erros))


# ── Consulta Prestado (notas emitidas) ────────────────────────────────────────


def consultar_nfse_prestado(
    empresa_nome: str,
    empresa_codigo: str,
    inscricao_municipal: str,
    cnpj: str,
    competencia_mes: int,
    competencia_ano: int,
) -> list[NfseData]:
    """
    Consulta todas as NFS-e emitidas (Serviço Prestado) de uma empresa
    para um período de competência, com paginação automática.

    Args:
        empresa_nome: Nome da empresa (para logs)
        empresa_codigo: Código/IM da empresa (para logs)
        inscricao_municipal: Inscrição Municipal do prestador
        cnpj: CNPJ do prestador
        competencia_mes: Mês de competência (1-12)
        competencia_ano: Ano de competência

    Returns:
        Lista de NfseData (todas as páginas combinadas)

    Raises:
        NfseServiceError: Para erros de negócio do webservice
        zeep.exceptions.Fault: Para erros de protocolo SOAP
    """
    log_info(
        empresa_nome,
        empresa_codigo,
        "NFSe Prestado",
        f"Consultando NFSe emitidas — {competencia_mes:02d}/{competencia_ano}",
    )

    client = get_client()
    all_notas: list[NfseData] = []
    pagina = 1

    while True:
        params = build_consultar_prestado_dict(
            inscricao_municipal=inscricao_municipal,
            cnpj=cnpj,
            competencia_mes=competencia_mes,
            competencia_ano=competencia_ano,
            pagina=pagina,
        )
        # _params captura o valor atual (evita captura tardia em lambda de loop)
        _params = params

        try:
            def _call_prestado():
                client.service.ConsultarNfseServicoPrestado(
                    ConsultarNfseServicoPrestadoEnvio=_params
                )
                return client.get_last_received_body()

            resp_str = _chamar_soap_com_retry(
                "NFSe Prestado", empresa_nome, empresa_codigo, _call_prestado
            )
        except Fault as f:
            log_error(empresa_nome, empresa_codigo, "NFSe Prestado SOAP Fault", str(f))
            raise

        notas_dicts, erros, proxima_pagina = parse_nfse_list_response(resp_str)

        if erros:
            if _apenas_sem_registro(erros):
                log_warning(
                    empresa_nome,
                    empresa_codigo,
                    "NFSe Prestado",
                    f"Nenhuma NFS-e emitida em {competencia_mes:02d}/{competencia_ano}.",
                )
                break
            log_error(empresa_nome, empresa_codigo, "NFSe Prestado", "; ".join(erros))
            raise NfseServiceError(erros)

        page_notas = [NfseData.from_dict(d) for d in notas_dicts]
        all_notas.extend(page_notas)

        log_info(
            empresa_nome,
            empresa_codigo,
            "NFSe Prestado",
            f"Página {pagina}: {len(page_notas)} nota(s). Total: {len(all_notas)}",
        )

        if not proxima_pagina or proxima_pagina <= pagina:
            break
        pagina = proxima_pagina

    return all_notas


# ── Consulta Tomado (notas recebidas) ─────────────────────────────────────────


def consultar_nfse_tomado(
    empresa_nome: str,
    empresa_codigo: str,
    cnpj_cpf: str,
    inscricao_municipal: str,
    competencia_mes: int,
    competencia_ano: int,
) -> list[NfseData]:
    """
    Consulta todas as NFS-e recebidas (Serviço Tomado) de uma empresa
    para um período de competência, com paginação automática.

    Args:
        empresa_nome: Nome da empresa (para logs)
        empresa_codigo: Código/IM da empresa (para logs)
        cnpj_cpf: CNPJ ou CPF do tomador
        inscricao_municipal: Inscrição Municipal do tomador
        competencia_mes: Mês de competência (1-12)
        competencia_ano: Ano de competência

    Returns:
        Lista de NfseData (todas as páginas combinadas)
    """
    log_info(
        empresa_nome,
        empresa_codigo,
        "NFSe Tomado",
        f"Consultando NFSe recebidas — {competencia_mes:02d}/{competencia_ano}",
    )

    client = get_client()
    all_notas: list[NfseData] = []
    pagina = 1

    while True:
        params = build_consultar_tomado_dict(
            cnpj_cpf=cnpj_cpf,
            inscricao_municipal=inscricao_municipal,
            competencia_mes=competencia_mes,
            competencia_ano=competencia_ano,
            pagina=pagina,
        )
        _params = params

        try:
            def _call_tomado():
                client.service.ConsultarNfseServicoTomado(
                    ConsultarNfseServicoTomadoEnvio=_params
                )
                return client.get_last_received_body()

            resp_str = _chamar_soap_com_retry(
                "NFSe Tomado", empresa_nome, empresa_codigo, _call_tomado
            )
        except Fault as f:
            log_error(empresa_nome, empresa_codigo, "NFSe Tomado SOAP Fault", str(f))
            raise

        notas_dicts, erros, proxima_pagina = parse_nfse_list_response(resp_str)

        if erros:
            if _apenas_sem_registro(erros):
                log_warning(
                    empresa_nome,
                    empresa_codigo,
                    "NFSe Tomado",
                    f"Nenhuma NFS-e recebida em {competencia_mes:02d}/{competencia_ano}.",
                )
                break
            log_error(empresa_nome, empresa_codigo, "NFSe Tomado", "; ".join(erros))
            raise NfseServiceError(erros)

        page_notas = [NfseData.from_dict(d) for d in notas_dicts]
        all_notas.extend(page_notas)

        log_info(
            empresa_nome,
            empresa_codigo,
            "NFSe Tomado",
            f"Página {pagina}: {len(page_notas)} nota(s). Total: {len(all_notas)}",
        )

        if not proxima_pagina or proxima_pagina <= pagina:
            break
        pagina = proxima_pagina

    return all_notas


# ── Consulta Retroativa ────────────────────────────────────────────────────────


def consultar_retroativo(
    empresa_nome: str,
    empresa_codigo: str,
    cnpj_cpf: str,
    inscricao_municipal: str,
    competencia_str: str,
    meses_retroativos: int = RETROACTIVE_MONTHS,
) -> dict[str, dict[str, list[NfseData]]]:
    """
    Consulta retroativa: para cada um dos N meses anteriores à competência
    informada, consulta Prestado e Tomado.

    Substitui o retroactive_service.py da automação antiga (que baixava PDFs).
    Agora retorna dados estruturados para serem salvos como XML.

    Args:
        empresa_nome: Nome da empresa
        empresa_codigo: Código/IM da empresa
        cnpj_cpf: CNPJ ou CPF
        inscricao_municipal: Inscrição Municipal
        competencia_str: Competência de referência no formato "MM/YYYY"
        meses_retroativos: Quantos meses retroativos consultar (padrão: 6)

    Returns:
        Dict com chave "MMYYYY" e valor {"prestado": [...], "tomado": [...]}
        Inclui apenas os meses onde pelo menos uma nota foi encontrada.
    """
    dt_base = datetime.strptime(competencia_str, "%m/%Y")
    results: dict[str, dict[str, list[NfseData]]] = {}

    for delta in range(1, meses_retroativos + 1):
        total_months = (dt_base.year * 12 + dt_base.month) - 1 - delta
        year = total_months // 12
        month = (total_months % 12) + 1
        chave = f"{month:02d}{year}"

        log_info(
            empresa_nome,
            empresa_codigo,
            "Retroativa",
            f"Consultando período retroativo: {month:02d}/{year}",
        )

        prestado: list[NfseData] = []
        tomado: list[NfseData] = []

        try:
            prestado = consultar_nfse_prestado(
                empresa_nome, empresa_codigo, inscricao_municipal, cnpj_cpf, month, year
            )
        except Exception as exc:
            log_warning(
                empresa_nome,
                empresa_codigo,
                "Retroativa Prestado",
                f"Erro em {month:02d}/{year}: {exc}",
            )

        try:
            tomado = consultar_nfse_tomado(
                empresa_nome, empresa_codigo, cnpj_cpf, inscricao_municipal, month, year
            )
        except Exception as exc:
            log_warning(
                empresa_nome,
                empresa_codigo,
                "Retroativa Tomado",
                f"Erro em {month:02d}/{year}: {exc}",
            )

        if prestado or tomado:
            results[chave] = {"prestado": prestado, "tomado": tomado}

    return results


# ── Consulta por faixa de número (operação documentada no manual JP) ──────────


def consultar_nfse_faixa(
    empresa_nome: str,
    empresa_codigo: str,
    inscricao_municipal: str,
    cnpj: str,
    numero_inicial: int = 1,
    numero_final: int = 999999999,
) -> list[NfseData]:
    """
    Consulta NFS-e por faixa de número (ConsultarNfseFaixa).

    Operação documentada no manual da Prefeitura de João Pessoa.
    Use como alternativa a consultar_nfse_prestado quando o servidor
    não suportar ConsultarNfseServicoPrestado.

    Para pegar todas as notas do prestador, use a faixa padrão (1 a 999999999)
    e filtre por competência no resultado.

    Returns:
        Lista de NfseData de todas as páginas.
    """
    log_info(empresa_nome, empresa_codigo, "NFSe Faixa",
             f"Consultando por faixa {numero_inicial}-{numero_final}")

    client = get_client()
    all_notas: list[NfseData] = []
    pagina = 1

    while True:
        params = build_consultar_faixa_dict(
            inscricao_municipal=inscricao_municipal,
            cnpj=cnpj,
            numero_inicial=numero_inicial,
            numero_final=numero_final,
            pagina=pagina,
        )
        _params = params

        try:
            def _call_faixa():
                client.service.ConsultarNfseFaixa(
                    ConsultarNfseFaixaEnvio=_params
                )
                return client.get_last_received_body()

            resp_str = _chamar_soap_com_retry(
                "NFSe Faixa", empresa_nome, empresa_codigo, _call_faixa
            )
        except Fault as f:
            log_error(empresa_nome, empresa_codigo, "NFSe Faixa SOAP Fault", str(f))
            raise

        notas_dicts, erros, proxima_pagina = parse_nfse_list_response(resp_str)

        if erros:
            if _apenas_sem_registro(erros):
                break
            log_error(empresa_nome, empresa_codigo, "NFSe Faixa", "; ".join(erros))
            raise NfseServiceError(erros)

        page_notas = [NfseData.from_dict(d) for d in notas_dicts]
        all_notas.extend(page_notas)

        log_info(empresa_nome, empresa_codigo, "NFSe Faixa",
                 f"Página {pagina}: {len(page_notas)} nota(s). Total: {len(all_notas)}")

        if not proxima_pagina or proxima_pagina <= pagina:
            break
        pagina = proxima_pagina

    return all_notas


# ── Helpers ────────────────────────────────────────────────────────────────────


def _apenas_sem_registro(erros: list[str]) -> bool:
    """
    Verifica se todos os erros são do tipo "nenhum registro encontrado",
    que não é um erro real — apenas ausência de dados.
    """
    for erro in erros:
        if not any(codigo in erro for codigo in _CODIGOS_SEM_REGISTRO):
            return False
    return True
