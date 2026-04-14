"""
Utilitários de montagem e parsing XML para o webservice SISMJP (ABRASF 2.03).

Os métodos SOAP ConsultarNfseServicoPrestado e ConsultarNfseServicoTomado
recebem dois parâmetros de string XML:
  - nfseCabecMsg: cabeçalho com versão
  - nfseDadosMsg: corpo da consulta (montado pelas funções build_* abaixo)
"""

import calendar
from datetime import date
from typing import Optional

from lxml import etree

from config.settings import ABRASF_VERSION, CODIGO_MUNICIPIO

# ── Cabeçalho ─────────────────────────────────────────────────────────────────


def build_cabecalho() -> str:
    """
    Monta o cabeçalho padrão ABRASF 2.03.

    Retorna:
        String XML: <cabecalho versao="2.03"><versaoDados>2.03</versaoDados></cabecalho>
    """
    cab = etree.Element("cabecalho", versao=ABRASF_VERSION)
    etree.SubElement(cab, "versaoDados").text = ABRASF_VERSION
    return etree.tostring(cab, encoding="unicode")


# ── Builders de consulta ───────────────────────────────────────────────────────


def build_consultar_nfse_servico_prestado(
    inscricao_municipal: str,
    cnpj: str,
    competencia_mes: int,
    competencia_ano: int,
    pagina: int = 1,
) -> str:
    """
    Monta XML para ConsultarNfseServicoPrestado (notas emitidas).

    Schema ABRASF 2.03:
        ConsultarNfseServicoPrestadoEnvio
          └─ Prestador
               ├─ CpfCnpj / Cnpj
               └─ InscricaoMunicipal
          └─ PeriodoEmissao
               ├─ DataInicial
               └─ DataFinal
          └─ Pagina

    Args:
        inscricao_municipal: IM do prestador no município
        cnpj: CNPJ do prestador (14 dígitos, sem formatação)
        competencia_mes: Mês (1-12)
        competencia_ano: Ano (ex: 2025)
        pagina: Página para paginação (começa em 1)
    """
    first_day = date(competencia_ano, competencia_mes, 1)
    last_day = date(
        competencia_ano,
        competencia_mes,
        calendar.monthrange(competencia_ano, competencia_mes)[1],
    )

    root = etree.Element("ConsultarNfseServicoPrestadoEnvio")

    prestador = etree.SubElement(root, "Prestador")
    cpf_cnpj_el = etree.SubElement(prestador, "CpfCnpj")
    cnpj_clean = _digits_only(cnpj)
    if len(cnpj_clean) == 14:
        etree.SubElement(cpf_cnpj_el, "Cnpj").text = cnpj_clean
    else:
        etree.SubElement(cpf_cnpj_el, "Cpf").text = cnpj_clean
    etree.SubElement(prestador, "InscricaoMunicipal").text = inscricao_municipal.strip()

    periodo = etree.SubElement(root, "PeriodoEmissao")
    etree.SubElement(periodo, "DataInicial").text = first_day.strftime("%Y-%m-%d")
    etree.SubElement(periodo, "DataFinal").text = last_day.strftime("%Y-%m-%d")

    etree.SubElement(root, "Pagina").text = str(pagina)

    return etree.tostring(root, encoding="unicode")


def build_consultar_nfse_faixa(
    inscricao_municipal: str,
    cnpj: str,
    numero_inicial: int = 1,
    numero_final: int = 999999999,
    pagina: int = 1,
) -> str:
    """
    Monta XML para ConsultarNfseFaixa (notas por faixa de número).

    Operação documentada no manual da Prefeitura de João Pessoa.
    Útil quando ConsultarNfseServicoPrestado não estiver disponível.

    Para consultar todas as notas de um prestador: use numero_inicial=1
    e numero_final=999999999 (faixa ampla) e filtre por data no cliente.

    Schema:
        ConsultarNfseFaixaEnvio
          └─ Prestador / CpfCnpj / InscricaoMunicipal
          └─ Faixa / NumeroNfseInicial / NumeroNfseFinal
          └─ Pagina
    """
    root = etree.Element("ConsultarNfseFaixaEnvio")

    prestador = etree.SubElement(root, "Prestador")
    cpf_cnpj_el = etree.SubElement(prestador, "CpfCnpj")
    cnpj_clean = _digits_only(cnpj)
    if len(cnpj_clean) == 14:
        etree.SubElement(cpf_cnpj_el, "Cnpj").text = cnpj_clean
    else:
        etree.SubElement(cpf_cnpj_el, "Cpf").text = cnpj_clean
    etree.SubElement(prestador, "InscricaoMunicipal").text = inscricao_municipal.strip()

    faixa = etree.SubElement(root, "Faixa")
    etree.SubElement(faixa, "NumeroNfseInicial").text = str(numero_inicial)
    etree.SubElement(faixa, "NumeroNfseFinal").text = str(numero_final)

    etree.SubElement(root, "Pagina").text = str(pagina)

    return etree.tostring(root, encoding="unicode")


def build_consultar_nfse_por_rps(
    numero_rps: str,
    serie_rps: str,
    tipo_rps: int,
    inscricao_municipal: str,
    cnpj: str,
) -> str:
    """
    Monta XML para ConsultarNfsePorRps (busca nota pelo RPS que a originou).

    Schema:
        ConsultarNfseRpsEnvio
          └─ IdentificacaoRps / Numero / Serie / Tipo
          └─ Prestador / CpfCnpj / InscricaoMunicipal
    """
    root = etree.Element("ConsultarNfseRpsEnvio")

    id_rps = etree.SubElement(root, "IdentificacaoRps")
    etree.SubElement(id_rps, "Numero").text = numero_rps
    etree.SubElement(id_rps, "Serie").text = serie_rps
    etree.SubElement(id_rps, "Tipo").text = str(tipo_rps)

    prestador = etree.SubElement(root, "Prestador")
    cpf_cnpj_el = etree.SubElement(prestador, "CpfCnpj")
    cnpj_clean = _digits_only(cnpj)
    if len(cnpj_clean) == 14:
        etree.SubElement(cpf_cnpj_el, "Cnpj").text = cnpj_clean
    else:
        etree.SubElement(cpf_cnpj_el, "Cpf").text = cnpj_clean
    etree.SubElement(prestador, "InscricaoMunicipal").text = inscricao_municipal.strip()

    return etree.tostring(root, encoding="unicode")


def build_consultar_nfse_servico_tomado(
    cnpj_cpf: str,
    inscricao_municipal: str,
    competencia_mes: int,
    competencia_ano: int,
    pagina: int = 1,
) -> str:
    """
    Monta XML para ConsultarNfseServicoTomado (notas recebidas).

    Schema ABRASF 2.03:
        ConsultarNfseServicoTomadoEnvio
          └─ Tomador
               ├─ CpfCnpj / (Cnpj | Cpf)
               └─ InscricaoMunicipal  (opcional para PJ)
          └─ PeriodoEmissao
               ├─ DataInicial
               └─ DataFinal
          └─ Pagina

    Args:
        cnpj_cpf: CNPJ (14 dígitos) ou CPF (11 dígitos) do tomador
        inscricao_municipal: IM do tomador (pode ser vazio para empresas de fora do município)
        competencia_mes: Mês (1-12)
        competencia_ano: Ano (ex: 2025)
        pagina: Página para paginação
    """
    first_day = date(competencia_ano, competencia_mes, 1)
    last_day = date(
        competencia_ano,
        competencia_mes,
        calendar.monthrange(competencia_ano, competencia_mes)[1],
    )

    root = etree.Element("ConsultarNfseServicoTomadoEnvio")

    tomador = etree.SubElement(root, "Tomador")
    cpf_cnpj_el = etree.SubElement(tomador, "CpfCnpj")
    doc_clean = _digits_only(cnpj_cpf)
    if len(doc_clean) == 14:
        etree.SubElement(cpf_cnpj_el, "Cnpj").text = doc_clean
    else:
        etree.SubElement(cpf_cnpj_el, "Cpf").text = doc_clean
    if inscricao_municipal and inscricao_municipal.strip():
        etree.SubElement(tomador, "InscricaoMunicipal").text = inscricao_municipal.strip()

    periodo = etree.SubElement(root, "PeriodoEmissao")
    etree.SubElement(periodo, "DataInicial").text = first_day.strftime("%Y-%m-%d")
    etree.SubElement(periodo, "DataFinal").text = last_day.strftime("%Y-%m-%d")

    etree.SubElement(root, "Pagina").text = str(pagina)

    return etree.tostring(root, encoding="unicode")


# ── Builders de dict para API tipada do zeep ─────────────────────────────────
# Usados em vez dos builders de string quando se chama client.service.*()
# diretamente. O zeep serializa os dicts nos elementos corretos (com namespace
# resolvido pelo WSDL). O _SignaturePlugin assina depois da serialização.


def build_consultar_prestado_dict(
    inscricao_municipal: str,
    cnpj: str,
    competencia_mes: int,
    competencia_ano: int,
    pagina: int = 1,
) -> dict:
    """Retorna dict de parâmetros para ConsultarNfseServicoPrestado (zeep typed API)."""
    first_day = date(competencia_ano, competencia_mes, 1)
    last_day = date(
        competencia_ano,
        competencia_mes,
        calendar.monthrange(competencia_ano, competencia_mes)[1],
    )
    cnpj_clean = _digits_only(cnpj)
    cpf_cnpj = {"Cnpj": cnpj_clean} if len(cnpj_clean) == 14 else {"Cpf": cnpj_clean}
    return {
        "Prestador": {
            "CpfCnpj": cpf_cnpj,
            "InscricaoMunicipal": inscricao_municipal.strip(),
        },
        "PeriodoEmissao": {
            "DataInicial": first_day,
            "DataFinal": last_day,
        },
        "Pagina": pagina,
    }


def build_consultar_tomado_dict(
    cnpj_cpf: str,
    inscricao_municipal: str,
    competencia_mes: int,
    competencia_ano: int,
    pagina: int = 1,
) -> dict:
    """Retorna dict de parâmetros para ConsultarNfseServicoTomado (zeep typed API)."""
    first_day = date(competencia_ano, competencia_mes, 1)
    last_day = date(
        competencia_ano,
        competencia_mes,
        calendar.monthrange(competencia_ano, competencia_mes)[1],
    )
    doc_clean = _digits_only(cnpj_cpf)
    cpf_cnpj = {"Cnpj": doc_clean} if len(doc_clean) == 14 else {"Cpf": doc_clean}
    tomador: dict = {"CpfCnpj": cpf_cnpj}
    if inscricao_municipal and inscricao_municipal.strip():
        tomador["InscricaoMunicipal"] = inscricao_municipal.strip()
    return {
        "Tomador": tomador,
        "PeriodoEmissao": {
            "DataInicial": first_day,
            "DataFinal": last_day,
        },
        "Pagina": pagina,
    }


def build_consultar_faixa_dict(
    inscricao_municipal: str,
    cnpj: str,
    numero_inicial: int = 1,
    numero_final: int = 999999999,
    pagina: int = 1,
) -> dict:
    """Retorna dict de parâmetros para ConsultarNfseFaixa (zeep typed API)."""
    cnpj_clean = _digits_only(cnpj)
    cpf_cnpj = {"Cnpj": cnpj_clean} if len(cnpj_clean) == 14 else {"Cpf": cnpj_clean}
    return {
        "Prestador": {
            "CpfCnpj": cpf_cnpj,
            "InscricaoMunicipal": inscricao_municipal.strip(),
        },
        "Faixa": {
            "NumeroNfseInicial": numero_inicial,
            "NumeroNfseFinal": numero_final,
        },
        "Pagina": pagina,
    }


# ── Parser de resposta ────────────────────────────────────────────────────────


def parse_nfse_list_response(
    xml_string: str | bytes,
) -> tuple[list[dict], list[str], int]:
    """
    Faz o parse da resposta de ConsultarNfseServicoPrestado ou Tomado.

    Returns:
        (notas, erros, proxima_pagina)
        - notas: lista de dicts com campos da NFS-e (ver NfseData.from_dict)
        - erros: lista de mensagens de erro (vazia se OK)
        - proxima_pagina: número da próxima página, ou 0 se não houver mais
    """
    if isinstance(xml_string, bytes):
        xml_string = xml_string.decode("utf-8", errors="replace")

    # Remover BOM e espaços iniciais
    xml_string = xml_string.strip().lstrip("\ufeff")

    try:
        root = etree.fromstring(xml_string.encode("utf-8"))
    except etree.XMLSyntaxError as exc:
        return [], [f"Resposta inválida (não é XML): {exc}"], 0

    # ── Checar erros de negócio (ListaMensagemRetorno) ────────────────────
    erros: list[str] = []
    for msg_el in root.iter("MensagemRetorno"):
        codigo = _text(msg_el, "Codigo")
        descricao = _text(msg_el, "Mensagem") or _text(msg_el, "Descricao")
        correcao = _text(msg_el, "Correcao")
        texto = f"[{codigo}] {descricao}"
        if correcao:
            texto += f" → {correcao}"
        erros.append(texto)

    if erros:
        return [], erros, 0

    # ── Extrair CompNfse ──────────────────────────────────────────────────
    notas: list[dict] = []
    for comp_el in root.iter("CompNfse"):
        nota = _parse_comp_nfse(comp_el)
        if nota:
            notas.append(nota)

    # ── Paginação ─────────────────────────────────────────────────────────
    proxima_pagina = 0
    pg_el = root.find(".//ProximaPagina")
    if pg_el is not None and pg_el.text:
        try:
            proxima_pagina = int(pg_el.text.strip())
        except ValueError:
            proxima_pagina = 0

    return notas, [], proxima_pagina


def _parse_comp_nfse(comp_el: etree._Element) -> Optional[dict]:
    """Extrai campos de um elemento <CompNfse>."""
    # Localiza o InfNfse — pode estar em Nfse/InfNfse ou direto em InfNfse
    inf = comp_el.find(".//InfNfse")
    if inf is None:
        return None

    prestador = inf.find("PrestadorServico") or inf.find("Prestador")
    tomador = inf.find("TomadorServico") or inf.find("Tomador")
    servico = inf.find("Servico")
    valores = servico.find("Valores") if servico is not None else None

    nota = {
        "numero": _text(inf, "Numero"),
        "codigo_verificacao": _text(inf, "CodigoVerificacao"),
        "data_emissao": _text(inf, "DataEmissao"),
        "competencia": _text(inf, "Competencia"),
        "status": _text(inf, "Situacao") or _text(inf, "NaturezaOperacao"),
        # Prestador
        "prestador_cnpj": _cpf_cnpj(prestador, "CpfCnpj") if prestador is not None else "",
        "prestador_im": _text(prestador, "InscricaoMunicipal") if prestador is not None else "",
        "prestador_nome": _text(prestador, "RazaoSocial") if prestador is not None else "",
        # Tomador
        "tomador_cnpj": (
            _cpf_cnpj(tomador.find("IdentificacaoTomador"), "CpfCnpj")
            if tomador is not None and tomador.find("IdentificacaoTomador") is not None
            else _cpf_cnpj(tomador, "CpfCnpj") if tomador is not None else ""
        ),
        "tomador_nome": _text(tomador, "RazaoSocial") if tomador is not None else "",
        # Serviço
        "descricao_servico": _text(servico, "Discriminacao") if servico is not None else "",
        "codigo_servico": _text(servico, "ItemListaServico") if servico is not None else "",
        # Valores
        "valor_servicos": _float(valores, "ValorServicos"),
        "valor_deducoes": _float(valores, "ValorDeducoes"),
        "base_calculo": _float(valores, "BaseCalculo"),
        "aliquota": _float(valores, "Aliquota"),
        "valor_iss": _float(valores, "ValorIss"),
        "iss_retido": _text(valores, "IssRetido") if valores is not None else "2",
        "valor_pis": _float(valores, "ValorPis"),
        "valor_cofins": _float(valores, "ValorCofins"),
        "valor_inss": _float(valores, "ValorInss"),
        "valor_ir": _float(valores, "ValorIr"),
        "valor_csll": _float(valores, "ValorCsll"),
        "valor_liquido": _float(valores, "ValorLiquidoNfse"),
        # XML bruto para SIEG
        "_xml_compnfse": etree.tostring(comp_el, encoding="unicode"),
    }
    return nota


# ── Builder de XML agregado para salvar em disco / enviar ao SIEG ─────────────


def build_nfse_xml_file(
    notas: list[dict],
    tipo: str,
    empresa_nome: str,
    competencia: str,
) -> str:
    """
    Cria um XML agregando todos os CompNfse de uma lista de notas.
    Usado para salvar o arquivo em disco e enviar ao SIEG.

    Args:
        notas: Lista de dicts com campo '_xml_compnfse'
        tipo: "Emitidas" ou "Recebidas"
        empresa_nome: Nome da empresa
        competencia: Período de competência (ex: "04/2025" ou "042025")

    Returns:
        String XML com declaração e todas as CompNfse aninhadas
    """
    root = etree.Element(
        "ListaNfse",
        tipo=tipo,
        empresa=empresa_nome,
        competencia=competencia,
        municipio=CODIGO_MUNICIPIO,
        padrao=f"ABRASF {ABRASF_VERSION}",
    )

    for nota in notas:
        xml_comp = nota.get("_xml_compnfse", "")
        if xml_comp:
            try:
                child = etree.fromstring(xml_comp.encode("utf-8"))
                root.append(child)
            except etree.XMLSyntaxError:
                pass

    return etree.tostring(
        root,
        encoding="unicode",
        xml_declaration=False,
        pretty_print=True,
    )


# ── Helpers privados ──────────────────────────────────────────────────────────


def _text(element: Optional[etree._Element], tag: str) -> str:
    """Retorna o texto de um subelemento ou string vazia."""
    if element is None:
        return ""
    child = element.find(tag)
    return (child.text or "").strip() if child is not None else ""


def _float(element: Optional[etree._Element], tag: str) -> float:
    """Retorna o valor float de um subelemento ou 0.0."""
    raw = _text(element, tag)
    try:
        return float(raw) if raw else 0.0
    except ValueError:
        return 0.0


def _cpf_cnpj(element: Optional[etree._Element], tag: str) -> str:
    """Extrai CNPJ ou CPF de dentro de um bloco CpfCnpj."""
    if element is None:
        return ""
    block = element.find(tag)
    if block is None:
        return ""
    cnpj = block.find("Cnpj")
    if cnpj is not None and cnpj.text:
        return cnpj.text.strip()
    cpf = block.find("Cpf")
    if cpf is not None and cpf.text:
        return cpf.text.strip()
    return ""


def _digits_only(value: str) -> str:
    """Remove tudo que não for dígito."""
    return "".join(c for c in value if c.isdigit())
