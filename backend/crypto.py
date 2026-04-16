"""
Utilitários de criptografia para proteção das senhas dos certificados.
Utiliza Fernet (AES-128-CBC + HMAC-SHA256) do pacote cryptography.
"""
import os
import base64
from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv

load_dotenv()


def _get_fernet() -> Fernet:
    """
    Retorna a instância do Fernet usando a SECRET_KEY do ambiente.
    A chave deve ser uma Fernet key válida (base64url-encoded, 32 bytes).
    """
    secret_key = os.getenv("SECRET_KEY")
    if not secret_key:
        raise EnvironmentError(
            "SECRET_KEY não definida no ambiente. "
            "Gere uma chave com: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(secret_key.encode())


def criptografar_senha(senha: str) -> str:
    """
    Criptografa a senha do certificado para armazenamento seguro no banco.

    Args:
        senha: senha em texto claro

    Returns:
        String criptografada (base64url-encoded) para armazenar no banco
    """
    fernet = _get_fernet()
    token = fernet.encrypt(senha.encode("utf-8"))
    return token.decode("utf-8")


def descriptografar_senha(senha_encrypted: str) -> str:
    """
    Descriptografa a senha do certificado recuperada do banco.

    Args:
        senha_encrypted: string criptografada armazenada no banco

    Returns:
        Senha em texto claro para uso na abertura do .pfx

    Raises:
        ValueError: se a senha não puder ser descriptografada (token inválido ou chave errada)
    """
    fernet = _get_fernet()
    try:
        return fernet.decrypt(senha_encrypted.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        raise ValueError(
            "Não foi possível descriptografar a senha do certificado. "
            "Verifique se a SECRET_KEY não mudou desde o cadastro da empresa."
        )


def gerar_nova_chave() -> str:
    """
    Utilitário para gerar uma nova Fernet key.
    Use apenas durante o setup inicial da aplicação.
    """
    return Fernet.generate_key().decode()
