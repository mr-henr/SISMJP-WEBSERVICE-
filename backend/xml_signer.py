"""
Assinatura digital XML/DSig conforme ABRASF 2.04 — implementação manual.

Por que não usar signxml ou cryptography.hazmat diretamente?
- signxml >= 3.x bloqueia SHA1 por padrão (exige configuração extra)
- OpenSSL 3.x (usado pelo cryptography) desabilita SHA1 no nível de segurança padrão
- pycryptodome é uma biblioteca Python pura (sem OpenSSL) e suporta RSA-SHA1 sem restrições

Especificações do padrão ABRASF 2.04:
  - Método: XMLDSig Enveloped Signature
  - Canonicalização: C14N  http://www.w3.org/TR/2001/REC-xml-c14n-20010315
  - Algoritmo de assinatura: RSA-SHA1
  - Algoritmo de digest: SHA1
  - Transforms: enveloped-signature + C14N
"""

import hashlib
import base64
from lxml import etree
from cryptography.hazmat.primitives import serialization
from cryptography.x509 import Certificate
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

# pycryptodome: RSA-SHA1 puro Python, sem dependência do OpenSSL
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA1
from Crypto.PublicKey import RSA as _PycRSA

# ─── Constantes XMLDSig ───────────────────────────────────────────────────────

DS_NS    = "http://www.w3.org/2000/09/xmldsig#"
C14N_ALG = "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
RSA_SHA1 = "http://www.w3.org/2000/09/xmldsig#rsa-sha1"
SHA1_URI = "http://www.w3.org/2000/09/xmldsig#sha1"
ENV_SIG  = "http://www.w3.org/2000/09/xmldsig#enveloped-signature"


# ─── Funções internas ─────────────────────────────────────────────────────────

def _c14n(element: etree._Element) -> bytes:
    """
    Canonicaliza um elemento lxml com C14N W3C 2001 (não-exclusivo).
    Quando o elemento faz parte de uma árvore, inclui as declarações
    de namespace herdadas dos ancestrais — exatamente o que ABRASF exige.
    """
    return etree.tostring(
        element,
        method="c14n",
        exclusive=False,
        with_comments=False
    )


def _sha1_b64(data: bytes) -> str:
    """Retorna o SHA1 de `data` codificado em base64."""
    return base64.b64encode(hashlib.sha1(data).digest()).decode()


def _rsa_sha1_sign(private_key: RSAPrivateKey, data: bytes) -> str:
    """
    Assina `data` com RSA-PKCS1v15 + SHA1 via pycryptodome.

    pycryptodome não passa pelo OpenSSL, portanto não está sujeito à
    política de segurança que bloqueia SHA1 no OpenSSL 3.x.
    """
    # Exportar a chave privada para PEM e reimportar via pycryptodome
    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    rsa_key = _PycRSA.import_key(key_pem)
    h = SHA1.new(data)
    sig_bytes = pkcs1_15.new(rsa_key).sign(h)
    return base64.b64encode(sig_bytes).decode()


def _cert_b64_der(certificate: Certificate) -> str:
    """Retorna o certificado X.509 em base64 (formato DER) para o KeyInfo."""
    der = certificate.public_bytes(serialization.Encoding.DER)
    return base64.b64encode(der).decode()


# ─── Assinatura principal ─────────────────────────────────────────────────────

def assinar_xml(
    xml_string: str,
    private_key: RSAPrivateKey,
    certificate: Certificate,
    reference_id: str = ""
) -> str:
    """
    Assina um XML string e retorna o XML assinado.

    Fluxo XMLDSig Enveloped:
      1. Localizar elemento a assinar (por Id ou raiz)
      2. C14N do elemento → SHA1 → DigestValue
      3. Montar <SignedInfo> com DigestValue
      4. C14N de <SignedInfo> → RSA-SHA1 → SignatureValue
      5. Montar <Signature> completo e inserir no elemento assinado

    Args:
        xml_string:   XML sem assinatura (produzido por xml_builder)
        private_key:  chave privada RSA do certificado A1
        certificate:  certificado X.509 do A1
        reference_id: Id do elemento a referenciar (sem '#').
                      String vazia = assina o documento inteiro (raiz).

    Returns:
        XML com <Signature> embutido, como string Unicode.
    """
    try:
        root = etree.fromstring(xml_string.encode("utf-8"))
    except etree.XMLSyntaxError as e:
        raise ValueError(f"XML inválido para assinatura: {e}")

    # ── 1. Localizar elemento a assinar ───────────────────────────────────────
    if reference_id:
        # Procurar pelo atributo Id (case-sensitive — ABRASF usa 'Id' maiúsculo)
        signed_elem = root.find(f'.//*[@Id="{reference_id}"]')
        if signed_elem is None:
            # Talvez seja a própria raiz
            if root.get("Id") == reference_id:
                signed_elem = root
            else:
                raise ValueError(
                    f"Elemento com Id='{reference_id}' não encontrado no XML. "
                    f"Verifique se xml_builder está gerando o atributo Id corretamente."
                )
        ref_uri = f"#{reference_id}"
    else:
        signed_elem = root
        ref_uri = ""

    # ── 2. Digest do elemento assinado ────────────────────────────────────────
    # Nota: como o <Signature> ainda não foi inserido, a transform
    # enveloped-signature (que remove o Signature) não precisa ser aplicada.
    c14n_content = _c14n(signed_elem)
    digest_value = _sha1_b64(c14n_content)

    # ── 3. Montar <SignedInfo> ────────────────────────────────────────────────
    # Usar nsmap para que lxml gere "xmlns=..." correto no C14N
    nsmap = {None: DS_NS}   # namespace default = DS_NS (sem prefixo)

    signed_info = etree.Element(f"{{{DS_NS}}}SignedInfo", nsmap=nsmap)

    c14n_method = etree.SubElement(signed_info, f"{{{DS_NS}}}CanonicalizationMethod")
    c14n_method.set("Algorithm", C14N_ALG)

    sig_method = etree.SubElement(signed_info, f"{{{DS_NS}}}SignatureMethod")
    sig_method.set("Algorithm", RSA_SHA1)

    ref_elem = etree.SubElement(signed_info, f"{{{DS_NS}}}Reference")
    ref_elem.set("URI", ref_uri)

    transforms = etree.SubElement(ref_elem, f"{{{DS_NS}}}Transforms")

    t1 = etree.SubElement(transforms, f"{{{DS_NS}}}Transform")
    t1.set("Algorithm", ENV_SIG)

    t2 = etree.SubElement(transforms, f"{{{DS_NS}}}Transform")
    t2.set("Algorithm", C14N_ALG)

    dig_method = etree.SubElement(ref_elem, f"{{{DS_NS}}}DigestMethod")
    dig_method.set("Algorithm", SHA1_URI)

    dig_value_elem = etree.SubElement(ref_elem, f"{{{DS_NS}}}DigestValue")
    dig_value_elem.text = digest_value

    # ── 4. Assinar SignedInfo ─────────────────────────────────────────────────
    c14n_signed_info = _c14n(signed_info)
    sig_value = _rsa_sha1_sign(private_key, c14n_signed_info)

    # ── 5. Montar <Signature> completo ────────────────────────────────────────
    signature = etree.Element(f"{{{DS_NS}}}Signature", nsmap=nsmap)
    signature.append(signed_info)

    sig_val_elem = etree.SubElement(signature, f"{{{DS_NS}}}SignatureValue")
    sig_val_elem.text = sig_value

    key_info = etree.SubElement(signature, f"{{{DS_NS}}}KeyInfo")
    x509_data = etree.SubElement(key_info, f"{{{DS_NS}}}X509Data")
    x509_cert = etree.SubElement(x509_data, f"{{{DS_NS}}}X509Certificate")
    x509_cert.text = _cert_b64_der(certificate)

    # ── 6. Inserir <Signature> no elemento assinado ───────────────────────────
    # ABRASF 2.04: a assinatura fica dentro do elemento referenciado
    signed_elem.append(signature)

    return etree.tostring(root, encoding="unicode", xml_declaration=False)
