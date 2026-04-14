"""
Script de teste mínimo para validar a comunicação com o webservice SISMJP
sem processar todas as empresas da planilha.

O que este script faz (em ordem):
  1. Carrega o certificado digital A1 (.pfx)
  2. Valida a conexão com o WSDL (local ou remoto)
  3. Lista as operações SOAP expostas pelo serviço
  4. Monta um XML de ConsultarNfseServicoPrestado com dados fixos
  5. Assina digitalmente o XML (XMLDSig RSA-SHA1)
  6. Envia a requisição e imprime a resposta bruta (primeiros 2000 chars)
  7. Faz o parse e mostra as notas retornadas ou a lista de erros

Uso:
    # Configure o .env com CERT_PATH, CERT_PASSWORD, USE_HOMOLOG=true
    # Edite as constantes TEST_* abaixo
    python testar_webservice.py

Este teste é IDEMPOTENTE — nunca altera dados na prefeitura, só consulta.

Saída esperada (feliz):
    [1/7] ✓ Certificado carregado
    [2/7] ✓ WSDL conectado — 7 operações disponíveis
    ...
    [7/7] ✓ N nota(s) encontrada(s)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Adiciona o diretório do script ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ─────────────────────────────────────────────────────────────────────────────
# PARÂMETROS DE TESTE — edite antes de rodar
# ─────────────────────────────────────────────────────────────────────────────

# Empresa real cadastrada na prefeitura (com procuração ativa no certificado):
TEST_INSCRICAO_MUNICIPAL = os.getenv("TEST_IM", "")      # ex: "123456"
TEST_CNPJ                = os.getenv("TEST_CNPJ", "")    # ex: "12345678000199" (só dígitos)
TEST_MES                 = int(os.getenv("TEST_MES", "1"))
TEST_ANO                 = int(os.getenv("TEST_ANO", "2025"))
TEST_PAGINA              = 1

# ─────────────────────────────────────────────────────────────────────────────


def _step(n: int, total: int, titulo: str):
    print(f"\n[{n}/{total}] {titulo}")
    print("─" * 66)


def _ok(msg: str):
    print(f"   ✓ {msg}")


def _err(msg: str):
    print(f"   ✗ {msg}")


def _info(msg: str):
    print(f"     {msg}")


def main() -> int:
    TOTAL = 7

    print("\n" + "═" * 66)
    print("  SISMJP — Teste mínimo de comunicação com o webservice")
    print("═" * 66)

    # Validação dos parâmetros de teste
    if not TEST_INSCRICAO_MUNICIPAL or not TEST_CNPJ:
        print("\n[ERRO] Defina as variáveis de ambiente TEST_IM e TEST_CNPJ")
        print("       ou edite as constantes no topo deste arquivo.\n")
        print("Exemplo (Linux/macOS):")
        print("       export TEST_IM=123456")
        print("       export TEST_CNPJ=12345678000199")
        print("       export TEST_MES=1 TEST_ANO=2025")
        print("       python testar_webservice.py\n")
        return 2

    # ── 1. Certificado ───────────────────────────────────────────────────────
    _step(1, TOTAL, "Carregando certificado digital A1")
    try:
        from config.settings import CERT_PATH, CERT_PASSWORD, USE_HOMOLOG, WEBSERVICE_URL
        from utils.cert_utils import load_pfx
        if not CERT_PATH or not Path(CERT_PATH).exists():
            _err(f"Certificado não encontrado: {CERT_PATH}")
            _info("Verifique CERT_PATH e CERT_PASSWORD no .env")
            return 3
        key_pem, cert_pem, _ = load_pfx(CERT_PATH, CERT_PASSWORD)
        _ok(f"Certificado carregado: {Path(CERT_PATH).name}")
        _info(f"Ambiente: {'HOMOLOGAÇÃO' if USE_HOMOLOG else 'PRODUÇÃO'}")
        _info(f"Endpoint: {WEBSERVICE_URL}")
    except Exception as exc:
        _err(f"Falha ao carregar certificado: {exc}")
        return 3

    # ── 2. Conexão com WSDL ──────────────────────────────────────────────────
    _step(2, TOTAL, "Conectando ao WSDL e inicializando cliente SOAP")
    try:
        from services.webservice_client import get_client
        client = get_client()
        _ok("Cliente SOAP inicializado")
    except SystemExit as exc:
        _err(str(exc))
        return 4
    except Exception as exc:
        _err(f"Falha ao inicializar cliente: {exc}")
        return 4

    # ── 3. Listar operações disponíveis ──────────────────────────────────────
    _step(3, TOTAL, "Operações SOAP expostas pelo serviço")
    try:
        ops = []
        for service in client._client.wsdl.services.values():
            for port in service.ports.values():
                for op_name in port.binding._operations.keys():
                    ops.append(op_name)
        if not ops:
            _err("Nenhuma operação encontrada no WSDL — possível WSDL corrompido")
            return 5
        for op in sorted(set(ops)):
            _info(f"• {op}")
        _ok(f"{len(set(ops))} operação(ões) disponível(is)")
    except Exception as exc:
        _err(f"Falha ao listar operações: {exc}")
        return 5

    # ── 4. Montar XML de consulta ────────────────────────────────────────────
    _step(4, TOTAL, f"Montando XML ConsultarNfseServicoPrestado ({TEST_MES:02d}/{TEST_ANO})")
    try:
        from utils.xml_utils import build_consultar_nfse_servico_prestado
        dados = build_consultar_nfse_servico_prestado(
            inscricao_municipal=TEST_INSCRICAO_MUNICIPAL,
            cnpj=TEST_CNPJ,
            competencia_mes=TEST_MES,
            competencia_ano=TEST_ANO,
            pagina=TEST_PAGINA,
        )
        _ok(f"XML montado ({len(dados)} bytes)")
        _info(f"Prestador IM: {TEST_INSCRICAO_MUNICIPAL} | CNPJ: {TEST_CNPJ}")
    except Exception as exc:
        _err(f"Falha ao montar XML: {exc}")
        return 6

    # ── 5. Assinar XML ────────────────────────────────────────────────────────
    _step(5, TOTAL, "Assinando XML (XMLDSig RSA-SHA1)")
    try:
        from utils.sign_utils import assinar_xml
        dados_assinado = assinar_xml(dados, key_pem, cert_pem)
        if "<Signature" not in dados_assinado:
            _err("Assinatura não foi inserida no XML")
            return 7
        _ok("XML assinado com sucesso")
    except Exception as exc:
        _err(f"Falha na assinatura: {exc}")
        return 7

    # ── 6. Enviar requisição SOAP (via call_raw — envelope bruto) ────────────
    _step(6, TOTAL, "Enviando requisição ConsultarNfseServicoPrestado")
    try:
        from zeep.exceptions import Fault
        try:
            resp_str = client.call_raw(dados_assinado)
        except Fault as f:
            _err(f"SOAP Fault: {f}")
            _info("Envelope enviado:")
            print(client.get_last_raw_sent()[:2000])
            return 8

        _ok(f"Resposta recebida ({len(resp_str)} bytes)")
        print("\n     ─── Primeiros 2000 chars da resposta ───")
        print(resp_str[:2000])
        print("     ─────────────────────────────────────────")
    except Exception as exc:
        _err(f"Falha na chamada SOAP: {type(exc).__name__}: {exc}")
        raw_sent = client.get_last_raw_sent()
        if raw_sent:
            print("\n     Último envelope enviado (primeiros 2000 chars):")
            print(raw_sent[:2000])
        return 8

    # ── 7. Parse da resposta ──────────────────────────────────────────────────
    _step(7, TOTAL, "Parseando resposta e extraindo notas")
    try:
        from utils.xml_utils import parse_nfse_list_response
        notas, erros, proxima = parse_nfse_list_response(resp_str)
        if erros:
            _info(f"ListaMensagemRetorno → {len(erros)} mensagem(ns):")
            for e in erros:
                _info(f"  • {e}")
            codigos_sem_registro = {"E10", "E4", "E15", "E56"}
            is_vazio = all(any(c in e for c in codigos_sem_registro) for e in erros)
            if is_vazio:
                _ok("Consulta OK — empresa sem NFS-e no período (resposta válida)")
                return 0
            return 9

        _ok(f"{len(notas)} nota(s) encontrada(s) — Próxima página: {proxima or 'nenhuma'}")
        for i, nota in enumerate(notas[:3], 1):
            print(f"\n     ── Nota #{i} ──")
            print(f"     Número         : {nota.get('numero', '')}")
            print(f"     Data emissão   : {nota.get('data_emissao', '')}")
            print(f"     Prestador      : {nota.get('prestador_nome', '')} ({nota.get('prestador_cnpj', '')})")
            print(f"     Tomador        : {nota.get('tomador_nome', '')} ({nota.get('tomador_cnpj', '')})")
            print(f"     Valor serviços : {nota.get('valor_servicos', 0.0):,.2f}")
            print(f"     Valor ISS      : {nota.get('valor_iss', 0.0):,.2f}")
        if len(notas) > 3:
            _info(f"... e mais {len(notas) - 3} nota(s) não exibidas")
        return 0
    except Exception as exc:
        _err(f"Falha no parse: {exc}")
        return 9


if __name__ == "__main__":
    code = main()
    print("\n" + "═" * 66)
    if code == 0:
        print("  TESTE CONCLUÍDO COM SUCESSO")
    else:
        print(f"  TESTE FALHOU (código {code})")
    print("═" * 66 + "\n")
    sys.exit(code)
