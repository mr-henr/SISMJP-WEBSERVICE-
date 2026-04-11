"""
Utilitários para carregamento do certificado digital ICP-Brasil A1 (.pfx/.p12).

O certificado é carregado, extraído para PEM em arquivos temporários e usado
para configurar mutual TLS na session do requests (que alimenta o zeep).
"""

import os
import tempfile
from pathlib import Path

import requests
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    pkcs12,
)


def load_pfx(cert_path: str, password: str) -> tuple[bytes, bytes, list[bytes]]:
    """
    Carrega arquivo .pfx/.p12 e retorna (chave_privada_pem, cert_pem, chain_pems).

    Args:
        cert_path: Caminho para o arquivo .pfx ou .p12
        password: Senha do certificado

    Returns:
        Tupla com (private_key_pem, certificate_pem, ca_chain_pems)

    Raises:
        FileNotFoundError: Se o arquivo não existir
        ValueError: Se a senha estiver errada ou o arquivo corrompido
    """
    pfx_file = Path(cert_path)
    if not pfx_file.exists():
        raise FileNotFoundError(f"Certificado não encontrado: {cert_path}")

    pfx_data = pfx_file.read_bytes()
    pwd_bytes = password.encode("utf-8") if isinstance(password, str) else password

    try:
        private_key, certificate, additional_certs = pkcs12.load_key_and_certificates(
            pfx_data, pwd_bytes
        )
    except Exception as exc:
        raise ValueError(
            f"Falha ao carregar certificado '{cert_path}'. "
            f"Verifique a senha e o formato do arquivo. Erro: {exc}"
        ) from exc

    key_pem = private_key.private_bytes(
        encoding=Encoding.PEM,
        format=PrivateFormat.PKCS8,
        encryption_algorithm=NoEncryption(),
    )
    cert_pem = certificate.public_bytes(Encoding.PEM)
    chain_pems = [c.public_bytes(Encoding.PEM) for c in (additional_certs or [])]

    return key_pem, cert_pem, chain_pems


class TempCertContext:
    """
    Gerenciador de contexto que escreve PEM em arquivos temporários e retorna
    os caminhos para uso com requests (parâmetro cert=(cert_file, key_file)).

    Os arquivos são deletados ao sair do contexto.

    Usage:
        ctx = TempCertContext(key_pem, cert_pem)
        ctx.setup()
        session.cert = ctx.cert_tuple
        # ... usar session ...
        ctx.cleanup()
    """

    def __init__(self, key_pem: bytes, cert_pem: bytes):
        self._key_pem = key_pem
        self._cert_pem = cert_pem
        self._cert_path: str | None = None
        self._key_path: str | None = None

    def setup(self) -> tuple[str, str]:
        """Cria arquivos temporários e retorna (cert_path, key_path)."""
        cert_tf = tempfile.NamedTemporaryFile(delete=False, suffix=".pem", mode="wb")
        cert_tf.write(self._cert_pem)
        cert_tf.flush()
        cert_tf.close()
        self._cert_path = cert_tf.name

        key_tf = tempfile.NamedTemporaryFile(delete=False, suffix=".pem", mode="wb")
        key_tf.write(self._key_pem)
        key_tf.flush()
        key_tf.close()
        self._key_path = key_tf.name

        return self._cert_path, self._key_path

    def cleanup(self):
        """Remove os arquivos temporários."""
        for path in (self._cert_path, self._key_path):
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except OSError:
                    pass

    @property
    def cert_tuple(self) -> tuple[str, str] | None:
        if self._cert_path and self._key_path:
            return self._cert_path, self._key_path
        return None

    def __enter__(self):
        self.setup()
        return self

    def __exit__(self, *args):
        self.cleanup()


def build_certified_session(cert_path: str, password: str) -> requests.Session:
    """
    Cria e retorna uma requests.Session com mutual TLS configurado a partir
    de um certificado A1 (.pfx).

    O TempCertContext é armazenado como atributo da session (_cert_ctx) para
    evitar que o GC delete os arquivos temporários antes do fim da session.
    Chame session._cert_ctx.cleanup() quando não precisar mais da session.

    Args:
        cert_path: Caminho para o .pfx/.p12
        password: Senha do certificado

    Returns:
        requests.Session com cert configurado para mutual TLS
    """
    key_pem, cert_pem, _ = load_pfx(cert_path, password)

    session = requests.Session()
    ctx = TempCertContext(key_pem, cert_pem)
    cert_file, key_file = ctx.setup()

    # Armazena contexto na session para evitar GC dos tempfiles
    session._cert_ctx = ctx  # type: ignore[attr-defined]
    session.cert = (cert_file, key_file)

    # Para produção: True (usa CA bundle do sistema ou certifi).
    # Se os CAs ICP-Brasil não estiverem instalados, passe o caminho para
    # o bundle PEM da ICP-Brasil: session.verify = "/path/icp-brasil-chain.pem"
    session.verify = True

    return session
