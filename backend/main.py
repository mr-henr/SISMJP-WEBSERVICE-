"""
NFS-e JP Manager - Aplicação FastAPI principal.

Serve tanto a API REST quanto os arquivos estáticos do frontend.
"""
import os
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv

# Carregar variáveis de ambiente do .env ao lado deste arquivo.
# override=True garante que o .env prevalece sobre variáveis do sistema.
load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Importar após load_dotenv para garantir que as variáveis estão disponíveis
from database import engine, Base
from routers import empresas, nfse, relatorio

# Criar tabelas do banco de dados na inicialização
Base.metadata.create_all(bind=engine)
logger.info("Banco de dados inicializado.")

# Verificar configuração crítica
ambiente = os.getenv("AMBIENTE", "producao")
secret_key = os.getenv("SECRET_KEY")
if not secret_key or secret_key == "SUBSTITUA-POR-UMA-CHAVE-FERNET-REAL":
    logger.warning(
        "⚠️  SECRET_KEY não configurada! Copie .env.example para .env e gere uma chave Fernet."
    )

logger.info(f"Ambiente: {ambiente.upper()}")

# ─── Criar aplicação FastAPI ───────────────────────────────────────────────────

app = FastAPI(
    title="NFS-e JP Manager",
    description=(
        "Sistema de gerenciamento de NFS-e para a Prefeitura de João Pessoa "
        "(GissOnline - ABRASF 2.04). Suporte multi-empresa com certificado A1."
    ),
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# ─── CORS ─────────────────────────────────────────────────────────────────────

cors_origins_str = os.getenv("CORS_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080")
cors_origins = [o.strip() for o in cors_origins_str.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers da API ───────────────────────────────────────────────────────────

app.include_router(empresas.router, prefix="/api/empresas", tags=["Empresas"])
app.include_router(nfse.router, prefix="/api/nfse", tags=["NFS-e"])
app.include_router(relatorio.router, prefix="/api/nfse", tags=["Relatório"])


@app.get("/api/health", tags=["Sistema"])
async def health_check():
    """Verifica o status da aplicação."""
    return {
        "status": "ok",
        "version": "1.0.0",
        "ambiente": ambiente,
        "secret_key_configurada": bool(secret_key and secret_key != "SUBSTITUA-POR-UMA-CHAVE-FERNET-REAL")
    }


# ─── Servir Frontend Estático ─────────────────────────────────────────────────

frontend_path = Path(__file__).parent.parent / "frontend"

if frontend_path.exists():
    # Servir assets estáticos (CSS, JS)
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_frontend():
        """Serve o index.html do frontend."""
        return FileResponse(str(frontend_path / "index.html"))

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend_fallback(full_path: str):
        """Fallback para SPA: qualquer rota não encontrada serve o index.html."""
        # Não redirecionar rotas da API
        if full_path.startswith("api/"):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        index_path = frontend_path / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return JSONResponse({"detail": "Frontend não encontrado"}, status_code=404)
else:
    logger.warning(f"Diretório frontend não encontrado: {frontend_path}")


# ─── Ponto de entrada ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    )
