"""
Modelo de dados para uma NFS-e (Nota Fiscal de Serviço Eletrônica).
Baseado no padrão ABRASF 2.03.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class NfseData:
    """Representa uma única NFS-e retornada pelo webservice SISMJP."""

    # ── Identificação ──────────────────────────────────────────────────────
    numero: str = ""
    codigo_verificacao: str = ""
    data_emissao: str = ""      # ISO: "YYYY-MM-DDTHH:MM:SS"
    competencia: str = ""       # ISO: "YYYY-MM-DD"
    status: str = ""            # "1"=Normal, "2"=Cancelada, "3"=Substituída

    # ── Prestador ──────────────────────────────────────────────────────────
    prestador_cnpj: str = ""
    prestador_im: str = ""      # InscricaoMunicipal
    prestador_nome: str = ""

    # ── Tomador ────────────────────────────────────────────────────────────
    tomador_cnpj: str = ""      # pode ser CPF quando PF
    tomador_nome: str = ""

    # ── Serviço ────────────────────────────────────────────────────────────
    descricao_servico: str = ""
    codigo_servico: str = ""    # ItemListaServico (LC 116)

    # ── Valores ────────────────────────────────────────────────────────────
    valor_servicos: float = 0.0
    valor_deducoes: float = 0.0
    base_calculo: float = 0.0
    aliquota: float = 0.0       # decimal (ex: 0.05 = 5%)
    valor_iss: float = 0.0
    iss_retido: str = "2"       # "1"=Sim, "2"=Não
    valor_pis: float = 0.0
    valor_cofins: float = 0.0
    valor_inss: float = 0.0
    valor_ir: float = 0.0
    valor_csll: float = 0.0
    valor_liquido: float = 0.0

    # ── XML bruto para upload SIEG ─────────────────────────────────────────
    xml_compnfse: str = ""

    # ── Propriedades calculadas ────────────────────────────────────────────

    @property
    def iss_retido_bool(self) -> bool:
        return self.iss_retido == "1"

    @property
    def iss_retido_str(self) -> str:
        return "Sim" if self.iss_retido_bool else "Não"

    @property
    def status_descricao(self) -> str:
        return {"1": "Normal", "2": "Cancelada", "3": "Substituída"}.get(
            str(self.status), str(self.status)
        )

    @property
    def data_emissao_fmt(self) -> str:
        """Data de emissão formatada como DD/MM/YYYY."""
        try:
            dt = datetime.fromisoformat(self.data_emissao.replace("Z", ""))
            return dt.strftime("%d/%m/%Y")
        except Exception:
            return self.data_emissao

    @property
    def competencia_fmt(self) -> str:
        """Competência formatada como MM/YYYY."""
        try:
            dt = datetime.fromisoformat(self.competencia[:10])
            return dt.strftime("%m/%Y")
        except Exception:
            return self.competencia

    @property
    def aliquota_pct(self) -> float:
        """Alíquota como percentual (ex: 0.05 → 5.0)."""
        return self.aliquota * 100.0

    # ── Construção a partir de dict (output do xml_utils.py) ──────────────

    @classmethod
    def from_dict(cls, d: dict) -> "NfseData":
        return cls(
            numero=d.get("numero", ""),
            codigo_verificacao=d.get("codigo_verificacao", ""),
            data_emissao=d.get("data_emissao", ""),
            competencia=d.get("competencia", ""),
            status=d.get("status", ""),
            prestador_cnpj=d.get("prestador_cnpj", ""),
            prestador_im=d.get("prestador_im", ""),
            prestador_nome=d.get("prestador_nome", ""),
            tomador_cnpj=d.get("tomador_cnpj", ""),
            tomador_nome=d.get("tomador_nome", ""),
            descricao_servico=d.get("descricao_servico", ""),
            codigo_servico=d.get("codigo_servico", ""),
            valor_servicos=float(d.get("valor_servicos", 0) or 0),
            valor_deducoes=float(d.get("valor_deducoes", 0) or 0),
            base_calculo=float(d.get("base_calculo", 0) or 0),
            aliquota=float(d.get("aliquota", 0) or 0),
            valor_iss=float(d.get("valor_iss", 0) or 0),
            iss_retido=d.get("iss_retido", "2"),
            valor_pis=float(d.get("valor_pis", 0) or 0),
            valor_cofins=float(d.get("valor_cofins", 0) or 0),
            valor_inss=float(d.get("valor_inss", 0) or 0),
            valor_ir=float(d.get("valor_ir", 0) or 0),
            valor_csll=float(d.get("valor_csll", 0) or 0),
            valor_liquido=float(d.get("valor_liquido", 0) or 0),
            xml_compnfse=d.get("_xml_compnfse", ""),
        )
