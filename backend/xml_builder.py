"""
Construção dos XMLs para cada operação NFS-e ABRASF 2.04.

Todos os métodos retornam uma tupla (xml_string, reference_id) onde:
- xml_string: XML pronto para assinatura
- reference_id: ID do elemento que será assinado (sem '#')
                String vazia = assinar o documento inteiro
"""
import calendar
from lxml import etree
from typing import Tuple, Optional
from schemas import (
    LoteRpsRequest, ConsultarLoteRequest, ConsultarPorRpsRequest,
    ConsultarFaixaRequest, CancelarNfseRequest, GerarNfseRequest,
    RpsDados, TomadorDados
)


def _elem(tag: str, text: str = None, **attribs) -> etree._Element:
    """Helper: cria um elemento lxml com texto e atributos opcionais."""
    el = etree.Element(tag, **attribs)
    if text is not None:
        el.text = str(text)
    return el


def _add(parent: etree._Element, tag: str, text: str = None, **attribs) -> etree._Element:
    """Helper: cria e adiciona elemento filho, retorna o filho."""
    el = etree.SubElement(parent, tag, **attribs)
    if text is not None:
        el.text = str(text)
    return el


def _build_cpfcnpj(parent: etree._Element, cpf: str = None, cnpj: str = None):
    """Helper: adiciona elemento CpfCnpj com CPF ou CNPJ."""
    cpfcnpj = _add(parent, "CpfCnpj")
    if cnpj:
        _add(cpfcnpj, "Cnpj", cnpj)
    elif cpf:
        _add(cpfcnpj, "Cpf", cpf)


def _build_tomador(parent: etree._Element, tomador: TomadorDados):
    """Helper: monta o bloco <Tomador> conforme schema ABRASF 2.04."""
    tom = _add(parent, "Tomador")

    # Identificação (CPF ou CNPJ)
    if tomador.cpf or tomador.cnpj:
        id_tom = _add(tom, "IdentificacaoTomador")
        _build_cpfcnpj(id_tom, cpf=tomador.cpf, cnpj=tomador.cnpj)

    _add(tom, "RazaoSocial", tomador.razao_social)

    if tomador.email:
        _add(tom, "Contato")
        # Estrutura correta: <Contato><Email>...</Email></Contato>
        contato = tom.find("Contato")
        _add(contato, "Email", tomador.email)

    if tomador.endereco:
        end = tomador.endereco
        end_elem = _add(tom, "Endereco")
        _add(end_elem, "Endereco", end.logradouro)
        _add(end_elem, "Numero", end.numero)
        if end.complemento:
            _add(end_elem, "Complemento", end.complemento)
        _add(end_elem, "Bairro", end.bairro)
        _add(end_elem, "CodigoMunicipio", end.codigo_municipio)
        _add(end_elem, "Uf", end.uf.upper())
        _add(end_elem, "Cep", end.cep)


def _build_rps_inf(parent: etree._Element, rps: RpsDados, cnpj_prestador: str,
                   inscricao_municipal: str, inf_id: str) -> etree._Element:
    """
    Monta o bloco <InfDeclaracaoPrestacaoServico Id="..."> conforme ABRASF 2.04.
    Retorna o elemento InfDeclaracaoPrestacaoServico.
    """
    inf = _add(parent, "InfDeclaracaoPrestacaoServico", Id=inf_id)

    # Identificação do RPS
    rps_elem = _add(inf, "Rps")
    id_rps = _add(rps_elem, "IdentificacaoRps")
    _add(id_rps, "Numero", rps.numero)
    _add(id_rps, "Serie", rps.serie)
    _add(id_rps, "Tipo", rps.tipo)
    _add(rps_elem, "DataEmissao", rps.data_emissao)
    _add(rps_elem, "Status", rps.status)

    _add(inf, "Competencia", rps.competencia)

    # Serviço
    servico = _add(inf, "Servico")
    valores = _add(servico, "Valores")
    _add(valores, "ValorServicos", rps.valor_servicos)
    _add(servico, "IssRetido", rps.iss_retido)
    _add(servico, "ItemListaServico", rps.item_lista_servico)
    if rps.codigo_cnae:
        _add(servico, "CodigoCnae", rps.codigo_cnae)
    _add(servico, "Discriminacao", rps.discriminacao)
    _add(servico, "CodigoMunicipio", rps.codigo_municipio)
    _add(servico, "ExigibilidadeISS", rps.exigibilidade_iss)
    _add(servico, "MunicipioIncidencia", rps.municipio_incidencia)

    # Prestador
    prestador = _add(inf, "Prestador")
    _build_cpfcnpj(prestador, cnpj=cnpj_prestador)
    _add(prestador, "InscricaoMunicipal", inscricao_municipal)

    # Tomador
    _build_tomador(inf, rps.tomador)

    _add(inf, "OptanteSimplesNacional", rps.optante_simples)
    _add(inf, "IncentivoFiscal", rps.incentivo_fiscal)

    return inf


# ─── Métodos públicos ─────────────────────────────────────────────────────────

def build_lote_rps_sincrono(dados: LoteRpsRequest, cnpj_prestador: str) -> Tuple[str, str]:
    """
    Monta XML para RecepcionarLoteRpsSincrono.
    A assinatura é aplicada no elemento LoteRps (reference_id = lote_id).
    """
    lote_id = f"Lote{dados.numero_lote}"

    root = _elem("EnviarLoteRpsSincronoEnvio")

    # LoteRps com Id para assinar
    lote = _add(root, "LoteRps", Id=lote_id, versao="2.04")
    _add(lote, "NumeroLote", dados.numero_lote)
    _build_cpfcnpj(lote, cnpj=cnpj_prestador)
    _add(lote, "InscricaoMunicipal", dados.inscricao_municipal)
    _add(lote, "QuantidadeRps", str(len(dados.lista_rps)))

    lista = _add(lote, "ListaRps")
    for i, rps in enumerate(dados.lista_rps, 1):
        rps_elem = _add(lista, "Rps")
        inf_id = f"Rps{rps.numero}"
        _build_rps_inf(rps_elem, rps, cnpj_prestador, dados.inscricao_municipal, inf_id)

    xml_str = etree.tostring(root, encoding="unicode", xml_declaration=False)
    return xml_str, lote_id


def build_lote_rps_assincrono(dados: LoteRpsRequest, cnpj_prestador: str) -> Tuple[str, str]:
    """
    Monta XML para RecepcionarLoteRps (assíncrono).
    Estrutura idêntica ao síncrono, apenas muda o elemento raiz.
    """
    lote_id = f"Lote{dados.numero_lote}"

    root = _elem("EnviarLoteRpsEnvio")

    lote = _add(root, "LoteRps", Id=lote_id, versao="2.04")
    _add(lote, "NumeroLote", dados.numero_lote)
    _build_cpfcnpj(lote, cnpj=cnpj_prestador)
    _add(lote, "InscricaoMunicipal", dados.inscricao_municipal)
    _add(lote, "QuantidadeRps", str(len(dados.lista_rps)))

    lista = _add(lote, "ListaRps")
    for rps in dados.lista_rps:
        rps_elem = _add(lista, "Rps")
        inf_id = f"Rps{rps.numero}"
        _build_rps_inf(rps_elem, rps, cnpj_prestador, dados.inscricao_municipal, inf_id)

    xml_str = etree.tostring(root, encoding="unicode", xml_declaration=False)
    return xml_str, lote_id


def build_consultar_lote(dados: ConsultarLoteRequest, cnpj_prestador: str) -> Tuple[str, str]:
    """Monta XML para ConsultarLoteRps. Assinatura cobre o documento inteiro (URI="")."""
    root = _elem("ConsultarLoteRpsEnvio")

    prestador = _add(root, "Prestador")
    _build_cpfcnpj(prestador, cnpj=cnpj_prestador)
    _add(prestador, "InscricaoMunicipal", dados.inscricao_municipal)

    _add(root, "Protocolo", dados.protocolo)

    xml_str = etree.tostring(root, encoding="unicode", xml_declaration=False)
    return xml_str, ""  # URI vazio = assina documento inteiro


def build_consultar_por_rps(dados: ConsultarPorRpsRequest, cnpj_prestador: str) -> Tuple[str, str]:
    """Monta XML para ConsultarNfsePorRps."""
    root = _elem("ConsultarNfseRpsEnvio")

    id_rps = _add(root, "IdentificacaoRps")
    _add(id_rps, "Numero", dados.numero)
    _add(id_rps, "Serie", dados.serie)
    _add(id_rps, "Tipo", dados.tipo)

    prestador = _add(root, "Prestador")
    _build_cpfcnpj(prestador, cnpj=cnpj_prestador)
    _add(prestador, "InscricaoMunicipal", dados.inscricao_municipal)

    xml_str = etree.tostring(root, encoding="unicode", xml_declaration=False)
    return xml_str, ""


def build_consultar_faixa(dados: ConsultarFaixaRequest, cnpj_prestador: str) -> Tuple[str, str]:
    """Monta XML para ConsultarNfseFaixa."""
    root = _elem("ConsultarNfseFaixaEnvio")

    prestador = _add(root, "Prestador")
    _build_cpfcnpj(prestador, cnpj=cnpj_prestador)
    _add(prestador, "InscricaoMunicipal", dados.inscricao_municipal)

    faixa = _add(root, "Faixa")
    _add(faixa, "NumeroNfseInicial", dados.numero_inicial)
    _add(faixa, "NumeroNfseFinal", dados.numero_final)

    _add(root, "Pagina", str(dados.pagina))

    xml_str = etree.tostring(root, encoding="unicode", xml_declaration=False)
    return xml_str, ""


def build_cancelar_nfse(dados: CancelarNfseRequest, cnpj_prestador: str) -> Tuple[str, str]:
    """
    Monta XML para CancelarNfse.
    A assinatura é aplicada em InfPedidoCancelamento (reference_id = "inf-cancelamento").
    """
    inf_id = "inf-cancelamento"

    root = _elem("CancelarNfseEnvio")
    pedido = _add(root, "Pedido")

    inf = _add(pedido, "InfPedidoCancelamento", Id=inf_id)

    id_nfse = _add(inf, "IdentificacaoNfse")
    _add(id_nfse, "Numero", dados.numero_nfse)
    _build_cpfcnpj(id_nfse, cnpj=cnpj_prestador)
    _add(id_nfse, "InscricaoMunicipal", dados.inscricao_municipal)
    _add(id_nfse, "CodigoMunicipio", dados.codigo_municipio)

    _add(inf, "CodigoCancelamento", dados.codigo_cancelamento)

    xml_str = etree.tostring(root, encoding="unicode", xml_declaration=False)
    return xml_str, inf_id


def build_gerar_nfse(dados: GerarNfseRequest, cnpj_prestador: str) -> Tuple[str, str]:
    """
    Monta XML para GerarNfse.
    A assinatura é aplicada em InfDeclaracaoPrestacaoServico.
    """
    inf_id = f"Rps{dados.rps.numero}"

    root = _elem("GerarNfseEnvio")
    rps_elem = _add(root, "Rps")

    _build_rps_inf(rps_elem, dados.rps, cnpj_prestador, dados.inscricao_municipal, inf_id)

    xml_str = etree.tostring(root, encoding="unicode", xml_declaration=False)
    return xml_str, inf_id


def build_consultar_servico_prestado(dados, cnpj_prestador: str, inscricao_municipal: str) -> Tuple[str, str]:
    """Monta XML para ConsultarNfseServicoPrestado com filtro de PeriodoCompetencia."""
    root = _elem("ConsultarNfseServicoPrestadoEnvio")

    prestador = _add(root, "Prestador")
    _build_cpfcnpj(prestador, cnpj=cnpj_prestador)
    _add(prestador, "InscricaoMunicipal", inscricao_municipal)

    ultimo_dia = calendar.monthrange(dados.competencia_ano, dados.competencia_mes)[1]
    data_inicial = f"{dados.competencia_ano:04d}-{dados.competencia_mes:02d}-01"
    data_final = f"{dados.competencia_ano:04d}-{dados.competencia_mes:02d}-{ultimo_dia:02d}"

    periodo = _add(root, "PeriodoCompetencia")
    _add(periodo, "DataInicial", data_inicial)
    _add(periodo, "DataFinal", data_final)

    _add(root, "Pagina", str(dados.pagina))

    xml_str = etree.tostring(root, encoding="unicode", xml_declaration=False)
    return xml_str, ""


def build_consultar_servico_tomado(dados, cnpj_tomador: str, inscricao_municipal: Optional[str] = None) -> Tuple[str, str]:
    """
    Monta XML para ConsultarNfseServicoTomado com filtro de PeriodoCompetencia.
    Identifica a empresa como TOMADOR do serviço.
    InscricaoMunicipal é opcional para o tomador (pode ser de outro município).
    """
    root = _elem("ConsultarNfseServicoTomadoEnvio")

    tomador = _add(root, "Tomador")
    _build_cpfcnpj(tomador, cnpj=cnpj_tomador)
    if inscricao_municipal:
        _add(tomador, "InscricaoMunicipal", inscricao_municipal)

    ultimo_dia = calendar.monthrange(dados.competencia_ano, dados.competencia_mes)[1]
    data_inicial = f"{dados.competencia_ano:04d}-{dados.competencia_mes:02d}-01"
    data_final = f"{dados.competencia_ano:04d}-{dados.competencia_mes:02d}-{ultimo_dia:02d}"

    periodo = _add(root, "PeriodoCompetencia")
    _add(periodo, "DataInicial", data_inicial)
    _add(periodo, "DataFinal", data_final)

    _add(root, "Pagina", str(dados.pagina))

    xml_str = etree.tostring(root, encoding="unicode", xml_declaration=False)
    return xml_str, ""
