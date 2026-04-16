"""
Modelos SQLAlchemy para o banco de dados.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from database import Base


class Empresa(Base):
    """
    Tabela de empresas cadastradas.
    Cada empresa possui seu próprio certificado A1 (.pfx).
    """
    __tablename__ = "empresas"

    id = Column(Integer, primary_key=True, index=True)
    cnpj = Column(String(14), unique=True, nullable=False, index=True,
                  comment="CNPJ apenas com números (14 dígitos)")
    razao_social = Column(String(150), nullable=False)
    inscricao_municipal = Column(String(20), nullable=True,
                                 comment="Inscrição Municipal no município de João Pessoa")
    caminho_certificado = Column(Text, nullable=False,
                                 comment="Caminho absoluto do arquivo .pfx no servidor")
    senha_certificado_encrypted = Column(Text, nullable=False,
                                         comment="Senha do .pfx criptografada com Fernet")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Empresa cnpj={self.cnpj} razao_social={self.razao_social}>"
