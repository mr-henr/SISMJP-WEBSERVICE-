"""
Router: Emissão de Relatório Fiscal em PDF.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import logging
from fastapi import APIRouter, Depends, HTTPException, Header, Response
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel, Field

from database import get_db
from models import Empresa
from relatorio import gerar_relatorio_pdf

logger = logging.getLogger(__name__)
router = APIRouter()


class RelatorioRequest(BaseModel):
    xml_notas: str = Field(..., description="XML combinado com as CompNfse já consultadas")
    tipo: str = Field(..., description="prestado | tomado")
    competencia_mes: int = Field(..., ge=1, le=12)
    competencia_ano: int = Field(..., ge=2000, le=2100)


@router.post("/relatorio-fiscal", response_class=Response)
def emitir_relatorio(
    dados: RelatorioRequest,
    db: Session = Depends(get_db),
    x_empresa_cnpj: Optional[str] = Header(None),
):
    """
    Gera e devolve o Relatório Fiscal em PDF a partir do XML de notas
    já consultado pelo frontend.
    """
    if not x_empresa_cnpj:
        raise HTTPException(
            status_code=400,
            detail="Header 'X-Empresa-CNPJ' obrigatório. Selecione uma empresa."
        )

    cnpj = x_empresa_cnpj.strip().replace(".", "").replace("/", "").replace("-", "")
    empresa = db.query(Empresa).filter(Empresa.cnpj == cnpj).first()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa não encontrada.")

    try:
        pdf_bytes = gerar_relatorio_pdf(
            xml_notas=dados.xml_notas,
            tipo=dados.tipo,
            competencia_mes=dados.competencia_mes,
            competencia_ano=dados.competencia_ano,
            razao_social=empresa.razao_social,
            cnpj=empresa.cnpj,
            inscricao_municipal=empresa.inscricao_municipal or "",
        )
    except Exception as e:
        logger.error(f"Erro ao gerar PDF: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao gerar o relatório PDF: {e}")

    mes_str = str(dados.competencia_mes).zfill(2)
    filename = f"relatorio-fiscal-{mes_str}-{dados.competencia_ano}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
