"""
Schemas Pydantic para validação de dados na API.
"""
from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime


# ─── Empresa ──────────────────────────────────────────────────────────────────

class EmpresaBase(BaseModel):
    cnpj: str = Field(..., min_length=14, max_length=14, description="CNPJ apenas com números")
    razao_social: str = Field(..., min_length=2, max_length=150)
    inscricao_municipal: Optional[str] = Field(None, max_length=20)
    caminho_certificado: str = Field(..., description="Caminho absoluto do .pfx no servidor")

    @validator("cnpj")
    def cnpj_apenas_numeros(cls, v):
        if not v.isdigit():
            raise ValueError("CNPJ deve conter apenas números")
        return v


class EmpresaCreate(EmpresaBase):
    senha_certificado: str = Field(..., min_length=1, description="Senha do .pfx (será criptografada)")


class EmpresaUpdate(BaseModel):
    razao_social: Optional[str] = None
    inscricao_municipal: Optional[str] = None
    caminho_certificado: Optional[str] = None
    senha_certificado: Optional[str] = None


class EmpresaResponse(EmpresaBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ─── Dados do RPS ─────────────────────────────────────────────────────────────

class TomadorEndereco(BaseModel):
    logradouro: str = Field(..., description="Nome da rua/avenida")
    numero: str = Field(..., description="Número do endereço")
    complemento: Optional[str] = None
    bairro: str
    codigo_municipio: str = Field(..., min_length=7, max_length=7, description="Código IBGE do município")
    uf: str = Field(..., min_length=2, max_length=2)
    cep: str = Field(..., min_length=8, max_length=8, description="CEP apenas com números")


class TomadorDados(BaseModel):
    cpf: Optional[str] = Field(None, min_length=11, max_length=11, description="CPF apenas com números")
    cnpj: Optional[str] = Field(None, min_length=14, max_length=14, description="CNPJ apenas com números")
    razao_social: str
    email: Optional[str] = None
    endereco: Optional[TomadorEndereco] = None

    @validator("cpf", "cnpj", pre=True, always=True)
    def valida_documento(cls, v):
        if v and not v.isdigit():
            raise ValueError("CPF/CNPJ deve conter apenas números")
        return v


class RpsDados(BaseModel):
    numero: str = Field(..., description="Número do RPS")
    serie: str = Field(..., max_length=5, description="Série do RPS (ex: A1)")
    tipo: str = Field("1", description="Tipo: 1=RPS, 2=Misto, 3=Cupom")
    data_emissao: str = Field(..., description="Data de emissão no formato YYYY-MM-DD")
    status: str = Field("1", description="Status: 1=Normal, 2=Cancelado")
    competencia: str = Field(..., description="Competência no formato YYYY-MM-DD")
    valor_servicos: str = Field(..., description="Valor dos serviços (ex: 1500.00)")
    iss_retido: str = Field("2", description="ISS Retido: 1=Sim, 2=Não")
    item_lista_servico: str = Field(..., description="Item da lista de serviços (ex: 01.01)")
    codigo_cnae: Optional[str] = Field(None, description="Código CNAE")
    discriminacao: str = Field(..., description="Descrição detalhada do serviço")
    codigo_municipio: str = Field(..., min_length=7, max_length=7, description="Código IBGE do município de prestação")
    exigibilidade_iss: str = Field("1", description="1=Exigível, 2=Não incidência, 3=Isenção, 4=Exportação, 5=Imunidade, 6=Suspenso por decisão judicial, 7=Suspenso por proc. adm.")
    municipio_incidencia: str = Field(..., min_length=7, max_length=7, description="Código IBGE do município de incidência")
    optante_simples: str = Field("2", description="1=Optante, 2=Não optante")
    incentivo_fiscal: str = Field("2", description="1=Sim, 2=Não")
    tomador: TomadorDados


# ─── Requisições da API ────────────────────────────────────────────────────────

class LoteRpsRequest(BaseModel):
    numero_lote: str = Field(..., description="Número único do lote")
    inscricao_municipal: Optional[str] = None
    lista_rps: list[RpsDados] = Field(..., min_items=1, max_items=50)


class ConsultarLoteRequest(BaseModel):
    protocolo: str = Field(..., description="Número do protocolo retornado pelo envio do lote")
    inscricao_municipal: Optional[str] = None


class ConsultarPorRpsRequest(BaseModel):
    numero: str
    serie: str
    tipo: str = "1"
    inscricao_municipal: Optional[str] = None


class ConsultarFaixaRequest(BaseModel):
    numero_inicial: str
    numero_final: str
    pagina: int = Field(1, ge=1)
    inscricao_municipal: Optional[str] = None


class CancelarNfseRequest(BaseModel):
    numero_nfse: str = Field(..., description="Número da NFS-e a cancelar")
    codigo_cancelamento: str = Field("1", description="1=Erro na emissão, 2=Serviço não prestado, 4=Emissão em duplicidade")
    inscricao_municipal: Optional[str] = None
    codigo_municipio: str = Field(..., min_length=7, max_length=7)


class GerarNfseRequest(BaseModel):
    inscricao_municipal: Optional[str] = None
    rps: RpsDados


class ConsultarServicoPrestadoRequest(BaseModel):
    competencia_mes: int = Field(..., ge=1, le=12, description="Mês da competência (1-12)")
    competencia_ano: int = Field(..., ge=2000, le=2100, description="Ano da competência")
    pagina: int = Field(1, ge=1)
    inscricao_municipal: Optional[str] = None
    tipo: str = Field("prestado", description="prestado = empresa como prestador | tomado = empresa como tomador")
    buscar_todas: bool = Field(True, description="True = percorre todas as páginas automaticamente; False = apenas a página informada")
