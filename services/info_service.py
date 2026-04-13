"""
Serviço de leitura da planilha de empresas (Auto_Prefeitura.xlsx).

Adaptado do info_service.py da automação antiga. Principal mudança:
adicionada leitura da coluna INSCRICAO_MUNICIPAL (opcional), necessária
para as consultas SOAP. Se ausente, usa CODIGO como fallback.

Esquema da planilha:
  Colunas de empresa (linhas de dados):
    - PROCESSO         → "S" para ativa
    - CODIGO           → Código/IM da empresa
    - CLIENTE          → Nome da empresa
    - CNPJ / CPF       → Documento (CNPJ ou CPF)
    - INSCRICAO_MUNICIPAL → (nova, opcional) IM para SOAP

  Células de configuração:
    - [0, 10] → pasta_base  (caminho de saída)
    - [4, 7]  → competência (MM/YYYY ou data Excel)
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd


def carregar_empresa(
    caminho_planilha: Path,
) -> tuple[list[str], list[str], list[str], list[str]]:
    """
    Lê a lista de empresas ativas da planilha.

    Returns:
        Tupla (codigos, nomes, cnpj_cpf_list, inscricoes_municipais)
        - codigos: lista de CODIGO
        - nomes: lista de CLIENTE
        - cnpj_cpf_list: lista de CNPJ / CPF
        - inscricoes_municipais: lista de INSCRICAO_MUNICIPAL (ou CODIGO como fallback)
    """
    df = pd.read_excel(str(caminho_planilha), dtype=str)
    df = df.dropna(how="all")

    empresas = df[
        df["PROCESSO"].notna()
        & (df["PROCESSO"].str.strip().str.upper() == "S")
        & df["CODIGO"].notna()
    ]

    has_im_col = "INSCRICAO_MUNICIPAL" in df.columns

    codigos: list[str] = []
    nomes: list[str] = []
    cnpj_cpf_list: list[str] = []
    inscricoes: list[str] = []

    for _, row in empresas.iterrows():
        cod = _safe_str(row.get("CODIGO", ""))
        if not cod:
            continue

        codigos.append(cod)
        nomes.append(_safe_str(row.get("CLIENTE", "")) or f"Empresa_{cod}")
        cnpj_cpf_list.append(_safe_str(row.get("CNPJ / CPF", "")))

        if has_im_col:
            im = _safe_str(row.get("INSCRICAO_MUNICIPAL", ""))
            inscricoes.append(im if im else cod)
        else:
            inscricoes.append(cod)

    return codigos, nomes, cnpj_cpf_list, inscricoes


def carregar_path_base(caminho_planilha: Path) -> tuple[str, str, str]:
    """
    Lê as configurações de pasta de saída e competência da planilha.

    As posições das células são as mesmas da automação antiga:
      - [0, 10] → pasta_base
      - [4, 7]  → competência

    Returns:
        Tupla (pasta_base, comp_path, competencia)
        - pasta_base: caminho da pasta raiz de saída
        - comp_path: competência sem separador (ex: "042025")
        - competencia: competência formatada (ex: "04/2025")
    """
    df = pd.read_excel(str(caminho_planilha), header=None)
    df = df.fillna("")

    pasta_base = str(df.iloc[0, 10]).strip()

    raw_comp = df.iloc[4, 7]
    if isinstance(raw_comp, (pd.Timestamp, datetime)):
        competencia = raw_comp.strftime("%m/%Y")
    else:
        competencia = str(raw_comp).strip()
        # Normaliza formatos como "4/2025" → "04/2025"
        if "/" in competencia:
            partes = competencia.split("/")
            if len(partes) == 2:
                competencia = f"{int(partes[0]):02d}/{partes[1]}"

    comp_path = competencia.replace("/", "")
    return pasta_base, comp_path, competencia


# ── Helpers ────────────────────────────────────────────────────────────────────


def _safe_str(value) -> str:
    """Converte um valor de célula para string limpa."""
    if value is None or (isinstance(value, float) and str(value) == "nan"):
        return ""
    s = str(value).strip()
    # Remove ".0" de valores numéricos lidos como float (ex: "12345.0" → "12345")
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    return s if s != "nan" else ""
