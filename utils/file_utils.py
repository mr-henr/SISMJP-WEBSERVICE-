"""
Utilitários de operações com arquivos.

Adaptado do file_utils.py da automação antiga — remove funções Playwright
(tentar_download, verificar_nome_arquivo) e adiciona funções para salvar
XMLs retornados pelo webservice em disco.
"""

import re
from pathlib import Path


def limpar_nome(nome: str) -> str:
    """Remove caracteres inválidos para uso em nomes de arquivo ou pasta."""
    return re.sub(r'[<>:"/\\|?*]', "", nome).strip()


def salvar_xml_nfse(
    xml_content: str,
    tipo: str,
    empresa_codigo: str,
    empresa_nome: str,
    comp_path: str,
    pasta_base: str,
) -> Path:
    """
    Salva o XML agregado de NFS-e em disco.

    Estrutura de pastas equivalente à automação antiga:
      - Prestador: {pasta_base}/Prestador/{codigo}-{nome}/{MMYYYY}/XML_Emitidas-{codigo}-{nome}.xml
      - Tomador:   {pasta_base}/Tomador/{codigo}-{nome}/{MMYYYY}/XML_Recebidas-{codigo}-{nome}.xml

    Args:
        xml_content: String XML com todas as CompNfse da competência
        tipo: "Prestador" (emitidas) ou "Tomador" (recebidas)
        empresa_codigo: Código/IM da empresa
        empresa_nome: Nome da empresa
        comp_path: Folder de competência (ex: "042025")
        pasta_base: Pasta raiz de saída

    Returns:
        Path do arquivo salvo
    """
    clean_nome = limpar_nome(empresa_nome)

    if tipo == "Prestador":
        filename = f"XML_Emitidas-{empresa_codigo}-{clean_nome}.xml"
        subdir = "Prestador"
    else:
        filename = f"XML_Recebidas-{empresa_codigo}-{clean_nome}.xml"
        subdir = "Tomador"

    out_dir = Path(pasta_base) / subdir / f"{empresa_codigo}-{clean_nome}" / comp_path
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / filename
    out_path.write_text(xml_content, encoding="utf-8")

    return out_path


def salvar_xml_retroativo(
    xml_content: str,
    tipo: str,
    empresa_codigo: str,
    empresa_nome: str,
    comp_path_retro: str,
    pasta_base: str,
) -> Path:
    """
    Salva XML retroativo em disco.

    Estrutura:
      {pasta_base}/Consulta Retroativa/{codigo}-{nome}/{MMYYYY}/
        XML_Emitidas-{codigo}-{nome}.xml  (Prestador)
        XML_Recebidas-{codigo}-{nome}.xml (Tomador)

    Args:
        xml_content: String XML com as CompNfse do período retroativo
        tipo: "Prestador" ou "Tomador"
        empresa_codigo: Código/IM da empresa
        empresa_nome: Nome da empresa
        comp_path_retro: Pasta do período retroativo (ex: "032025")
        pasta_base: Pasta raiz de saída

    Returns:
        Path do arquivo salvo
    """
    clean_nome = limpar_nome(empresa_nome)
    prefix = "XML_Emitidas" if tipo == "Prestador" else "XML_Recebidas"
    filename = f"{prefix}-{empresa_codigo}-{clean_nome}.xml"

    out_dir = (
        Path(pasta_base)
        / "Consulta Retroativa"
        / f"{empresa_codigo}-{clean_nome}"
        / comp_path_retro
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / filename
    out_path.write_text(xml_content, encoding="utf-8")

    return out_path
