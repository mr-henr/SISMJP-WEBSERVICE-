"""
Gerenciamento de certificados digitais A1 (.pfx / .p12).

Responsabilidades:
- Carregar o arquivo .pfx do disco
- Extrair chave privada e certificado X.509
- Exportar para PEM para uso no SSL/TLS e na assinatura XML
- Verificar validade do certificado
"""
import os
import tempfile
from datetime import datetime, timezone
from typing import Tuple, NamedTuple

from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.primitives import serialization
from cryptography.x509 import Certificate
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

from sqlalchemy.orm import Session
import models
from crypto import descriptografar_senha


class CertificadoCarregado(NamedTuple):
    """Container com os dados do certificado extraídos do .pfx."""
    private_key: RSAPrivateKey
    certificate: Certificate
    key_pem: bytes        # Chave privada em PEM (para requests/zeep)
    cert_pem: bytes       # Certificado em PEM (para requests/zeep)
    razao_social: str
    cnpj: str


def carregar_certificado(cnpj: str, db: Session) -> CertificadoCarregado:
    """
    Carrega e valida o certificado A1 de uma empresa pelo CNPJ.

    Fluxo:
    1. Busca empresa no banco pelo CNPJ
    2. Descriptografa a senha do certificado
    3. Lê o arquivo .pfx do disco
    4. Extrai chave privada e certificado X.509
    5. Verifica validade do certificado
    6. Retorna objeto CertificadoCarregado

    Args:
        cnpj: CNPJ da empresa (apenas números, 14 dígitos)
        db: Sessão do banco de dados

    Returns:
        CertificadoCarregado com chave privada, certificado e versões PEM

    Raises:
        ValueError: empresa não encontrada, arquivo não existe, ou certificado inválido
        FileNotFoundError: arquivo .pfx não encontrado no caminho cadastrado
    """
    # 1. Buscar empresa
    empresa = db.query(models.Empresa).filter(models.Empresa.cnpj == cnpj).first()
    if not empresa:
        raise ValueError(f"Empresa com CNPJ {cnpj} não encontrada no banco de dados.")

    # 2. Descriptografar senha
    try:
        senha = descriptografar_senha(empresa.senha_certificado_encrypted)
    except ValueError as e:
        raise ValueError(f"Erro ao descriptografar senha do certificado: {e}")

    # 3. Verificar se o arquivo .pfx existe
    if not os.path.exists(empresa.caminho_certificado):
        raise FileNotFoundError(
            f"Arquivo de certificado não encontrado: {empresa.caminho_certificado}\n"
            "Verifique o caminho cadastrado para a empresa."
        )

    # 4. Ler e carregar o .pfx
    with open(empresa.caminho_certificado, "rb") as f:
        pfx_data = f.read()

    try:
        private_key, certificate, chain = pkcs12.load_key_and_certificates(
            pfx_data,
            senha.encode("utf-8")
        )
    except Exception as e:
        raise ValueError(
            f"Não foi possível abrir o certificado .pfx. "
            f"Verifique se a senha está correta. Detalhe: {e}"
        )

    if private_key is None or certificate is None:
        raise ValueError("O arquivo .pfx não contém chave privada ou certificado válido.")

    # 5. Verificar validade do certificado
    now = datetime.now(timezone.utc)
    not_after = certificate.not_valid_after_utc if hasattr(certificate, 'not_valid_after_utc') else \
                certificate.not_valid_after.replace(tzinfo=timezone.utc)

    if now > not_after:
        raise ValueError(
            f"O certificado digital expirou em {not_after.strftime('%d/%m/%Y')}. "
            "Renove o certificado A1 antes de prosseguir."
        )

    # 6. Serializar para PEM (necessário para requests SSL e signxml)
    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    cert_pem = certificate.public_bytes(serialization.Encoding.PEM)

    return CertificadoCarregado(
        private_key=private_key,
        certificate=certificate,
        key_pem=key_pem,
        cert_pem=cert_pem,
        razao_social=empresa.razao_social,
        cnpj=cnpj
    )


def criar_arquivos_pem_temporarios(cert: CertificadoCarregado) -> Tuple[str, str]:
    """
    Cria arquivos temporários PEM no disco para uso com requests (mTLS).
    Os arquivos devem ser deletados após o uso.

    Returns:
        Tuple (caminho_cert_pem, caminho_key_pem)
    """
    # Arquivo do certificado
    cert_file = tempfile.NamedTemporaryFile(
        delete=False, suffix="_cert.pem", prefix="nfse_"
    )
    cert_file.write(cert.cert_pem)
    cert_file.close()

    # Arquivo da chave privada
    key_file = tempfile.NamedTemporaryFile(
        delete=False, suffix="_key.pem", prefix="nfse_"
    )
    key_file.write(cert.key_pem)
    key_file.close()

    return cert_file.name, key_file.name
