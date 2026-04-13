"""
Assinatura digital XMLDSig RSA-SHA1 para webservices ABRASF 2.03.

Padrão obrigatório em todas as prefeituras brasileiras ABRASF:
  - Algoritmo de canonicalização: C14N inclusiva (não exclusiva)
  - Algoritmo de assinatura: RSA-SHA1
  - Transform: enveloped-signature + C14N
  - KeyInfo: X509Certificate (DER em base64)

Dois modos de uso:
  - reference_uri=""    → assina o elemento raiz (consultas)
  - reference_uri="#id" → assina o elemento com Id="id" (emissão de RPS)
"""

import base64
import hashlib
from io import BytesIO

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.x509 import load_pem_x509_certificate
from lxml import etree

DSIG = "http://www.w3.org/2000/09/xmldsig#"
C14N_ALG = "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"


def _c14n(element: etree._Element) -> bytes:
    """C14N inclusiva de um elemento (sem comentários)."""
    buf = BytesIO()
    etree.ElementTree(element).write_c14n(buf, exclusive=False, with_comments=False)
    return buf.getvalue()


def assinar_xml(
    xml_string: str,
    key_pem: bytes,
    cert_pem: bytes,
    reference_uri: str = "",
) -> str:
    """
    Assina XML com XMLDSig RSA-SHA1 no padrão ABRASF 2.03.

    Args:
        xml_string   : XML a assinar (string UTF-8)
        key_pem      : chave privada PEM sem senha (bytes)
        cert_pem     : certificado PEM (bytes)
        reference_uri:
            ""    → assina o elemento raiz (consultas: ConsultarNfseFaixaEnvio, etc.)
            "#id" → assina o elemento com Id="id" (emissão: LoteRps, InfPedidoCancelamento…)

    Returns:
        XML com bloco <Signature> inserido no elemento correto.

    Raises:
        ValueError: Se reference_uri="#id" e o elemento não for encontrado.
    """
    private_key = load_pem_private_key(key_pem, password=None)
    cert_der = load_pem_x509_certificate(cert_pem).public_bytes(serialization.Encoding.DER)
    cert_b64 = base64.b64encode(cert_der).decode()

    root = etree.fromstring(xml_string.encode())

    # ── Localizar elemento alvo e onde inserir a Signature ────────────────
    if reference_uri.startswith("#"):
        ref_id = reference_uri[1:]
        target = next((e for e in root.iter() if e.get("Id") == ref_id), None)
        if target is None:
            raise ValueError(f"Elemento com Id='{ref_id}' não encontrado no XML")
        # Signature vai como irmão do elemento assinado (dentro do elemento pai)
        sig_parent = target.getparent() or root
    else:
        # Assina a raiz; Signature vai dentro da raiz
        target = root
        sig_parent = root

    # ── C14N do elemento alvo ─────────────────────────────────────────────
    # Transform enveloped-signature: remove Signature filhos antes de C14N
    target_copy = etree.fromstring(etree.tostring(target))
    for sig_el in target_copy.findall(f"{{{DSIG}}}Signature"):
        target_copy.remove(sig_el)
    digest_b64 = base64.b64encode(hashlib.sha1(_c14n(target_copy)).digest()).decode()

    # ── Construir SignedInfo ───────────────────────────────────────────────
    nsmap = {None: DSIG}
    si = etree.Element(f"{{{DSIG}}}SignedInfo", nsmap=nsmap)
    etree.SubElement(si, f"{{{DSIG}}}CanonicalizationMethod").set("Algorithm", C14N_ALG)
    etree.SubElement(si, f"{{{DSIG}}}SignatureMethod").set("Algorithm", f"{DSIG}rsa-sha1")
    ref = etree.SubElement(si, f"{{{DSIG}}}Reference")
    ref.set("URI", reference_uri)
    tr = etree.SubElement(ref, f"{{{DSIG}}}Transforms")
    etree.SubElement(tr, f"{{{DSIG}}}Transform").set("Algorithm", f"{DSIG}enveloped-signature")
    etree.SubElement(tr, f"{{{DSIG}}}Transform").set("Algorithm", C14N_ALG)
    etree.SubElement(ref, f"{{{DSIG}}}DigestMethod").set("Algorithm", f"{DSIG}sha1")
    etree.SubElement(ref, f"{{{DSIG}}}DigestValue").text = digest_b64

    # ── Assinar RSA-SHA1 do SignedInfo canonicalizado ─────────────────────
    sig_bytes = private_key.sign(_c14n(si), asym_padding.PKCS1v15(), hashes.SHA1())
    sig_b64 = base64.b64encode(sig_bytes).decode()

    # ── Montar elemento Signature completo ────────────────────────────────
    sig_elem = etree.Element(f"{{{DSIG}}}Signature", nsmap=nsmap)
    sig_elem.append(si)
    etree.SubElement(sig_elem, f"{{{DSIG}}}SignatureValue").text = sig_b64
    ki = etree.SubElement(sig_elem, f"{{{DSIG}}}KeyInfo")
    x509d = etree.SubElement(ki, f"{{{DSIG}}}X509Data")
    etree.SubElement(x509d, f"{{{DSIG}}}X509Certificate").text = cert_b64

    sig_parent.append(sig_elem)
    return etree.tostring(root, encoding="unicode", xml_declaration=False)
