"""
Automação SISMJP — Captura de NFS-e via Webservice ABRASF 2.03
Prefeitura de João Pessoa - PB

Substitui a automação Playwright anterior por consultas diretas ao
webservice SOAP do SISMJP. Processa todas as empresas da planilha
Auto_Prefeitura.xlsx e para cada uma:

  1. Consulta NFS-e emitidas (Serviço Prestado)
  2. Consulta NFS-e recebidas (Serviço Tomado)
  3. Gera Livro Fiscal Prestador (Excel)
  4. Gera Livro Fiscal Tomador (Excel)
  5. Salva XMLs em disco
  6. Consulta retroativa dos N meses anteriores
  7. Faz upload de tudo para o SIEG (pós-lote, com manifesto SHA256)
  8. Faz upload de tudo para o NIBO
"""

import io
import locale
import sys
from pathlib import Path

from config.settings import (
    OUTPUT_BASE_PATH,
    RETROACTIVE_MONTHS,
    SIEG_API_KEY,
    SPREADSHEET_PATH,
)
from models.nfse_model import NfseData
from services.fiscal_book_service import gerar_livro_fiscal
from services.info_service import carregar_empresa, carregar_path_base
from services.logging_service import configurar_log_file, log_error, log_info, log_warning
from services.nfse_service import (
    NfseServiceError,
    consultar_nfse_prestado,
    consultar_nfse_tomado,
    consultar_retroativo,
)
from services.nibo_service import upload_tudo_para_nibo
from services.sieg_service import upload_all_nfse
from services.webservice_client import get_client
from utils.file_utils import limpar_nome, salvar_xml_nfse, salvar_xml_retroativo
from utils.xml_utils import build_nfse_xml_file

# Força UTF-8 no console (importante no Windows)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


# ── Processamento por empresa ─────────────────────────────────────────────────


def processar_empresa(
    empresa_codigo: str,
    empresa_nome: str,
    cnpj_cpf: str,
    inscricao_municipal: str,
    competencia: str,
    comp_path: str,
    pasta_base: str,
):
    """
    Fluxo completo de processamento para uma empresa.

    Args:
        empresa_codigo: Código/IM da empresa
        empresa_nome: Nome da empresa
        cnpj_cpf: CNPJ ou CPF
        inscricao_municipal: Inscrição Municipal (para consultas SOAP)
        competencia: Período de competência no formato "MM/YYYY"
        comp_path: Pasta de competência (ex: "042025")
        pasta_base: Pasta raiz de saída
    """
    clean_nome = limpar_nome(empresa_nome)
    mes, ano = int(competencia.split("/")[0]), int(competencia.split("/")[1])

    print(f"\n{'=' * 60}")
    print(f"  Empresa: {empresa_nome} [{empresa_codigo}]")
    print(f"  Competência: {competencia}")
    print(f"{'=' * 60}")

    log_info(empresa_nome, empresa_codigo, "Início", "Iniciando processamento")

    # ── 1. NFSe emitidas (Prestado) ───────────────────────────────────────
    notas_prestado: list[NfseData] = []
    try:
        notas_prestado = consultar_nfse_prestado(
            empresa_nome=empresa_nome,
            empresa_codigo=empresa_codigo,
            inscricao_municipal=inscricao_municipal,
            cnpj=cnpj_cpf,
            competencia_mes=mes,
            competencia_ano=ano,
        )
        print(f"  [PRESTADO] {len(notas_prestado)} NFS-e emitida(s) encontrada(s)")
    except NfseServiceError as exc:
        print(f"  [PRESTADO] Erro de negócio: {exc}")
    except Exception as exc:
        log_error(empresa_nome, empresa_codigo, "Consulta Prestado", str(exc))
        print(f"  [PRESTADO] Erro na consulta: {exc}")

    # ── 2. NFSe recebidas (Tomado) ────────────────────────────────────────
    notas_tomado: list[NfseData] = []
    try:
        notas_tomado = consultar_nfse_tomado(
            empresa_nome=empresa_nome,
            empresa_codigo=empresa_codigo,
            cnpj_cpf=cnpj_cpf,
            inscricao_municipal=inscricao_municipal,
            competencia_mes=mes,
            competencia_ano=ano,
        )
        print(f"  [TOMADO]   {len(notas_tomado)} NFS-e recebida(s) encontrada(s)")
    except NfseServiceError as exc:
        print(f"  [TOMADO] Erro de negócio: {exc}")
    except Exception as exc:
        log_error(empresa_nome, empresa_codigo, "Consulta Tomado", str(exc))
        print(f"  [TOMADO] Erro na consulta: {exc}")

    # ── 3. Livro Fiscal Prestador ─────────────────────────────────────────
    try:
        caminho = gerar_livro_fiscal(
            notas=notas_prestado,
            tipo="Prestador",
            empresa_nome=empresa_nome,
            empresa_codigo=empresa_codigo,
            competencia=competencia,
            comp_path=comp_path,
            pasta_base=pasta_base,
        )
        if caminho:
            print(f"  [LIVRO PRESTADOR] Gerado → {caminho.name}")
    except Exception as exc:
        log_error(empresa_nome, empresa_codigo, "Livro Fiscal Prestador", str(exc))
        print(f"  [LIVRO PRESTADOR] Erro: {exc}")

    # ── 4. Livro Fiscal Tomador ───────────────────────────────────────────
    try:
        caminho = gerar_livro_fiscal(
            notas=notas_tomado,
            tipo="Tomador",
            empresa_nome=empresa_nome,
            empresa_codigo=empresa_codigo,
            competencia=competencia,
            comp_path=comp_path,
            pasta_base=pasta_base,
        )
        if caminho:
            print(f"  [LIVRO TOMADOR]   Gerado → {caminho.name}")
    except Exception as exc:
        log_error(empresa_nome, empresa_codigo, "Livro Fiscal Tomador", str(exc))
        print(f"  [LIVRO TOMADOR] Erro: {exc}")

    # ── 5. Salvar XMLs em disco ───────────────────────────────────────────
    if notas_prestado:
        try:
            xml = build_nfse_xml_file(notas_prestado, "Emitidas", empresa_nome, competencia)
            caminho_xml = salvar_xml_nfse(
                xml, "Prestador", empresa_codigo, clean_nome, comp_path, pasta_base
            )
            print(f"  [XML EMITIDAS]    Salvo → {caminho_xml.name}")
        except Exception as exc:
            log_error(empresa_nome, empresa_codigo, "Salvar XML Emitidas", str(exc))

    if notas_tomado:
        try:
            xml = build_nfse_xml_file(notas_tomado, "Recebidas", empresa_nome, competencia)
            caminho_xml = salvar_xml_nfse(
                xml, "Tomador", empresa_codigo, clean_nome, comp_path, pasta_base
            )
            print(f"  [XML RECEBIDAS]   Salvo → {caminho_xml.name}")
        except Exception as exc:
            log_error(empresa_nome, empresa_codigo, "Salvar XML Recebidas", str(exc))

    # ── 6. Consulta retroativa ────────────────────────────────────────────
    print(f"\n  [RETROATIVA] Consultando {RETROACTIVE_MONTHS} meses anteriores...")
    try:
        retro = consultar_retroativo(
            empresa_nome=empresa_nome,
            empresa_codigo=empresa_codigo,
            cnpj_cpf=cnpj_cpf,
            inscricao_municipal=inscricao_municipal,
            competencia_str=competencia,
            meses_retroativos=RETROACTIVE_MONTHS,
        )

        for comp_key, dados in retro.items():
            mes_retro = comp_key[:2]
            ano_retro = comp_key[2:]
            periodo = f"{mes_retro}/{ano_retro}"

            if dados["prestado"]:
                xml = build_nfse_xml_file(
                    dados["prestado"], "Emitidas", empresa_nome, periodo
                )
                p = salvar_xml_retroativo(
                    xml, "Prestador", empresa_codigo, clean_nome, comp_key, pasta_base
                )
                print(f"    → Retroativo {periodo} Prestado: {len(dados['prestado'])} nota(s) | {p.name}")

            if dados["tomado"]:
                xml = build_nfse_xml_file(
                    dados["tomado"], "Recebidas", empresa_nome, periodo
                )
                p = salvar_xml_retroativo(
                    xml, "Tomador", empresa_codigo, clean_nome, comp_key, pasta_base
                )
                print(f"    → Retroativo {periodo} Tomado:  {len(dados['tomado'])} nota(s) | {p.name}")

        if not retro:
            print("    → Nenhuma nota retroativa encontrada")

    except Exception as exc:
        log_error(empresa_nome, empresa_codigo, "Consulta Retroativa", str(exc))
        print(f"  [RETROATIVA] Erro: {exc}")

    log_info(empresa_nome, empresa_codigo, "Conclusão", "Processamento concluído")


# ── Ponto de entrada ──────────────────────────────────────────────────────────


def main():
    try:
        _configurar_locale()

        print("\n╔══════════════════════════════════════════════════════════╗")
        print("║   SISMJP — Automação via Webservice ABRASF 2.03         ║")
        print("║   Prefeitura de João Pessoa - PB                        ║")
        print("╚══════════════════════════════════════════════════════════╝\n")

        # ── Configurar log em arquivo ──────────────────────────────────────
        log_dir = Path(OUTPUT_BASE_PATH)
        log_dir.mkdir(parents=True, exist_ok=True)
        configurar_log_file(log_dir / "automacao_sismjp.log")

        # ── Carregar planilha ──────────────────────────────────────────────
        planilha = SPREADSHEET_PATH
        print(f"[CONFIG] Planilha: {planilha}")

        codigos, nomes, cnpj_cpf_list, inscricoes = carregar_empresa(planilha)
        pasta_base, comp_path, competencia = carregar_path_base(planilha)

        print(f"[CONFIG] Pasta de saída: {pasta_base}")
        print(f"[CONFIG] Competência: {competencia}")
        print(f"[CONFIG] Empresas ativas: {len(codigos)}\n")

        if not codigos:
            print("[AVISO] Nenhuma empresa ativa encontrada na planilha. Encerrando.")
            return

        # ── Inicializar cliente SOAP (valida certificado e WSDL) ──────────
        print("[WEBSERVICE] Inicializando cliente SOAP...")
        client = get_client()
        print("[WEBSERVICE] Cliente inicializado com sucesso.\n")

        # ── Processar cada empresa ─────────────────────────────────────────
        erros_criticos: list[str] = []
        for i in range(len(codigos)):
            try:
                processar_empresa(
                    empresa_codigo=codigos[i],
                    empresa_nome=nomes[i],
                    cnpj_cpf=cnpj_cpf_list[i],
                    inscricao_municipal=inscricoes[i],
                    competencia=competencia,
                    comp_path=comp_path,
                    pasta_base=pasta_base,
                )
            except Exception as exc:
                msg = f"{nomes[i]} [{codigos[i]}]: {exc}"
                log_error(nomes[i], codigos[i], "Processamento Geral", str(exc))
                erros_criticos.append(msg)
                print(f"\n[ERRO CRÍTICO] {msg}\n  → Continuando para próxima empresa...")
                continue

        # ── Upload SIEG (pós-lote) ─────────────────────────────────────────
        print("\n" + "─" * 60)
        if not SIEG_API_KEY:
            print("[SIEG] SIEG_API_KEY não configurada. Upload ignorado.")
        else:
            print("[SIEG] Iniciando upload pós-processamento...")
            resumo_sieg = upload_all_nfse(
                api_key=SIEG_API_KEY,
                pasta_base=pasta_base,
                timeout=60,
                retries=3,
                retry_backoff_sec=2.0,
                fail_fast=False,
            )
            print(
                f"[SIEG] Concluído — "
                f"Encontrados: {resumo_sieg['total_found']} | "
                f"Enviados: {resumo_sieg['sent_ok']} | "
                f"Pulados: {resumo_sieg['skipped']} | "
                f"Falhas: {resumo_sieg['sent_fail']}"
            )
            if resumo_sieg["fails"]:
                print("[SIEG] Arquivos com falha:")
                for f in resumo_sieg["fails"][:5]:
                    print(f"       {f['file']} → {f['error']}")

        # ── Upload NIBO ────────────────────────────────────────────────────
        print("\n[NIBO] Iniciando upload para o NIBO...")
        resumo_nibo = upload_tudo_para_nibo(pasta_base)
        print(f"[NIBO] Concluído — OK: {resumo_nibo['ok']} | Falhas: {resumo_nibo['fail']}")

        # ── Resumo final ───────────────────────────────────────────────────
        print("\n" + "═" * 60)
        print(f"  PROCESSAMENTO CONCLUÍDO")
        print(f"  Empresas processadas: {len(codigos)}")
        print(f"  Erros críticos: {len(erros_criticos)}")
        if erros_criticos:
            print("  Empresas com erro:")
            for e in erros_criticos:
                print(f"    • {e}")
        print("═" * 60 + "\n")

        # ── Liberar recursos ───────────────────────────────────────────────
        client.close()

    except SystemExit:
        raise
    except Exception as exc:
        log_error("Sistema", "N/A", "Erro Geral", str(exc))
        print(f"\n[ERRO FATAL] {exc}", file=sys.stderr)
        sys.exit(1)


def _configurar_locale():
    """Configura locale para formatação numérica (melhor esforço)."""
    for loc in ("pt_BR.UTF-8", "pt_BR", "en_US.UTF-8", "C.UTF-8", ""):
        try:
            locale.setlocale(locale.LC_ALL, loc)
            return
        except locale.Error:
            continue


if __name__ == "__main__":
    import locale
    main()
