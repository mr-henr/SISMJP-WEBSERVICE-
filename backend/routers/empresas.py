"""
Router de Empresas: CRUD completo para gerenciamento das empresas cadastradas.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import get_db
import models
from schemas import EmpresaCreate, EmpresaResponse, EmpresaUpdate
from crypto import criptografar_senha

router = APIRouter()


@router.get("/", response_model=List[EmpresaResponse])
def listar_empresas(db: Session = Depends(get_db)):
    """Lista todas as empresas cadastradas."""
    return db.query(models.Empresa).order_by(models.Empresa.razao_social).all()


@router.post("/", response_model=EmpresaResponse, status_code=status.HTTP_201_CREATED)
def criar_empresa(empresa: EmpresaCreate, db: Session = Depends(get_db)):
    """
    Cadastra uma nova empresa.
    A senha do certificado é criptografada com Fernet antes de salvar.
    """
    # Verificar CNPJ duplicado
    existente = db.query(models.Empresa).filter(models.Empresa.cnpj == empresa.cnpj).first()
    if existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Já existe uma empresa cadastrada com o CNPJ {empresa.cnpj}."
        )

    # Verificar se o arquivo .pfx existe no caminho informado
    if not os.path.exists(empresa.caminho_certificado):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Arquivo de certificado não encontrado: {empresa.caminho_certificado}"
        )

    # Criptografar a senha antes de salvar
    try:
        senha_encrypted = criptografar_senha(empresa.senha_certificado)
    except EnvironmentError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

    db_empresa = models.Empresa(
        cnpj=empresa.cnpj,
        razao_social=empresa.razao_social,
        inscricao_municipal=empresa.inscricao_municipal,
        caminho_certificado=empresa.caminho_certificado,
        senha_certificado_encrypted=senha_encrypted
    )
    db.add(db_empresa)
    db.commit()
    db.refresh(db_empresa)
    return db_empresa


@router.get("/{cnpj}", response_model=EmpresaResponse)
def buscar_empresa(cnpj: str, db: Session = Depends(get_db)):
    """Busca uma empresa pelo CNPJ."""
    empresa = db.query(models.Empresa).filter(models.Empresa.cnpj == cnpj).first()
    if not empresa:
        raise HTTPException(status_code=404, detail=f"Empresa com CNPJ {cnpj} não encontrada.")
    return empresa


@router.put("/{cnpj}", response_model=EmpresaResponse)
def atualizar_empresa(cnpj: str, dados: EmpresaUpdate, db: Session = Depends(get_db)):
    """Atualiza dados de uma empresa. Campos não informados são mantidos."""
    empresa = db.query(models.Empresa).filter(models.Empresa.cnpj == cnpj).first()
    if not empresa:
        raise HTTPException(status_code=404, detail=f"Empresa com CNPJ {cnpj} não encontrada.")

    if dados.razao_social is not None:
        empresa.razao_social = dados.razao_social

    if dados.inscricao_municipal is not None:
        empresa.inscricao_municipal = dados.inscricao_municipal

    if dados.caminho_certificado is not None:
        if not os.path.exists(dados.caminho_certificado):
            raise HTTPException(
                status_code=400,
                detail=f"Arquivo não encontrado: {dados.caminho_certificado}"
            )
        empresa.caminho_certificado = dados.caminho_certificado

    if dados.senha_certificado is not None:
        empresa.senha_certificado_encrypted = criptografar_senha(dados.senha_certificado)

    db.commit()
    db.refresh(empresa)
    return empresa


@router.delete("/{cnpj}", status_code=status.HTTP_204_NO_CONTENT)
def deletar_empresa(cnpj: str, db: Session = Depends(get_db)):
    """Remove uma empresa do cadastro."""
    empresa = db.query(models.Empresa).filter(models.Empresa.cnpj == cnpj).first()
    if not empresa:
        raise HTTPException(status_code=404, detail=f"Empresa com CNPJ {cnpj} não encontrada.")
    db.delete(empresa)
    db.commit()
