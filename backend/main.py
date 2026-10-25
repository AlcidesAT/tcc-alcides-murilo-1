"""
API HTTP do Sistema Inteligente de Consulta a Artigos Científicos.

Este módulo apenas monta a aplicação: middlewares, inicialização do banco,
rotas (em `routers/`) e o front-end estático. A lógica de recuperação, geração,
memória e avaliação fica no pacote `rag/`.

Perfis de acesso: Leitor (consulta, padrão), Participante (login da turma:
consulta + coleta de perguntas e avaliações para a pesquisa) e Administrador
(envio e gestão de artigos e acesso aos dados coletados).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import BASE_DIR, DOCUMENTS_DIR, LLM_MODEL
from database import init_db
from dependencies import get_rag
from routers import auth, chat, evaluation, interactions, library, survey


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
        print("[INFO] Banco de dados PostgreSQL inicializado.")
    except Exception as exc:
        print(f"[WARNING] Banco de dados PostgreSQL não disponível: {exc}")
        print("[WARNING] Arquivamento de metadados e avaliações desabilitados até que o BD esteja acessível.")
    get_rag()  # carrega o índice vetorial já na inicialização
    yield


app = FastAPI(
    title="Consulta Inteligente a Artigos Científicos",
    description="Sistema RAG para consulta em linguagem natural a artigos científicos.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def no_cache_frontend(request, call_next):
    """Evita que o navegador sirva versões antigas do front-end (HTML/CSS/JS).

    Em desenvolvimento, módulos ES são cacheados de forma agressiva; forçar a
    revalidação dispensa o 'hard refresh' a cada alteração."""
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.startswith("/static"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


@app.get("/api/health")
def health():
    return {"status": "ok", "documents_dir": str(DOCUMENTS_DIR), "llm_model": LLM_MODEL}


app.include_router(auth.router)
app.include_router(library.router)
app.include_router(chat.router)
app.include_router(evaluation.router)
app.include_router(survey.router)
app.include_router(interactions.router)


# ---------------------------------------------------------------------------
# Static files & frontend routes
# ---------------------------------------------------------------------------

FRONTEND_DIR = BASE_DIR / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    def root():
        return FileResponse(str(FRONTEND_DIR / "index.html"))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
