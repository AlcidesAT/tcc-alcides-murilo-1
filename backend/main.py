"""
API HTTP do Sistema Inteligente de Consulta a Artigos Científicos.

Expõe endpoints para upload e organização de artigos em pastas,
consulta em linguagem natural (opcionalmente restrita a uma pasta),
listagem e remoção de documentos e pastas, e arquivamento de artigos
no PostgreSQL, além de servir o front-end.

Perfis de acesso: Leitor (consulta, padrão) e Administrador (envio e gestão de
artigos, protegido por senha). O cadastro de múltiplos usuários no banco fica
para a segunda entrega do TCC.
"""

import json
import secrets
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import (
    ADMIN_PASSWORD,
    BASE_DIR,
    DEFAULT_FOLDER,
    DOCUMENTS_DIR,
    MAX_UPLOAD_MB,
    SUPPORTED_EXTENSIONS,
    slugify_folder,
)
from rag_service import RAGService
from database import SessionLocal, get_db, init_db
from models import Article, QuestionSource


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
        print("[INFO] Banco de dados PostgreSQL inicializado.")
    except Exception as exc:
        print(f"[WARNING] Banco de dados PostgreSQL não disponível: {exc}")
        print("[WARNING] Arquivamento de metadados desabilitado até que o BD esteja acessível.")
    yield


app = FastAPI(
    title="Consulta Inteligente a Artigos Científicos",
    description="Sistema RAG para consulta em linguagem natural a artigos científicos.",
    version="1.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

rag = RAGService()

# Token de sessão do administrador, gerado a cada inicialização do servidor.
# Quem informar a senha correta recebe este token e o reenvia no cabeçalho
# `X-Admin-Token` para acessar as rotas de gestão (upload, criação/remoção).
ADMIN_TOKEN = secrets.token_urlsafe(32)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class AskRequest(BaseModel):
    question: str
    folder: Optional[str] = None
    source: Optional[str] = None


class AskResponse(BaseModel):
    answer: str
    sources: list
    scope: str


class CreateFolderRequest(BaseModel):
    name: str


class AdminLoginRequest(BaseModel):
    password: str


# ---------------------------------------------------------------------------
# Autenticação do perfil Administrador
# ---------------------------------------------------------------------------

def require_admin(x_admin_token: Optional[str] = Header(default=None)):
    """Dependência que protege as rotas exclusivas do Administrador.

    O perfil Leitor (sem token) recebe 403 ao tentar enviar ou gerenciar
    artigos. A comparação usa `secrets.compare_digest` para evitar timing.
    """
    if not x_admin_token or not secrets.compare_digest(x_admin_token, ADMIN_TOKEN):
        raise HTTPException(
            status_code=403,
            detail="Ação restrita ao Administrador. Faça login para continuar.",
        )


@app.post("/api/admin/login")
def admin_login(payload: AdminLoginRequest):
    """Valida a senha do Administrador e devolve o token de sessão."""
    if not secrets.compare_digest(payload.password or "", ADMIN_PASSWORD):
        raise HTTPException(status_code=401, detail="Senha de administrador incorreta.")
    return {"token": ADMIN_TOKEN, "role": "admin"}


# ---------------------------------------------------------------------------
# Articles archive endpoint
# ---------------------------------------------------------------------------

@app.get("/api/articles")
def list_articles(
    folder: Optional[str] = None,
    db: Session = Depends(get_db),
):
    try:
        query = db.query(Article)
        if folder:
            query = query.filter(Article.folder == slugify_folder(folder))
        articles = query.order_by(Article.uploaded_at.desc()).all()
        return {
            "articles": [
                {
                    "id": str(a.id),
                    "folder": a.folder,
                    "filename": a.filename,
                    "file_size": a.file_size,
                    "file_type": a.file_type,
                    "chunks_indexed": a.chunks_indexed,
                    "uploaded_at": a.uploaded_at.isoformat(),
                }
                for a in articles
            ]
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Banco de dados indisponível: {exc}") from exc


# ---------------------------------------------------------------------------
# Existing endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok", "documents_dir": str(DOCUMENTS_DIR)}


@app.get("/api/folders")
def list_folders():
    indexed = rag.list_folders()
    indexed_names = {f["folder"] for f in indexed}
    for path in DOCUMENTS_DIR.iterdir():
        if path.is_dir() and path.name not in indexed_names:
            indexed.append({"folder": path.name, "chunks": 0, "documents": 0})
    indexed.sort(key=lambda f: f["folder"])
    return {"folders": indexed}


@app.post("/api/folders", status_code=201, dependencies=[Depends(require_admin)])
def create_folder(payload: CreateFolderRequest):
    raw = (payload.name or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="Nome da pasta é obrigatório.")

    folder_slug = slugify_folder(raw)
    folder_dir = DOCUMENTS_DIR / folder_slug
    if folder_dir.exists():
        raise HTTPException(status_code=409, detail=f"A pasta '{folder_slug}' já existe.")
    folder_dir.mkdir(parents=True, exist_ok=False)
    return {"folder": folder_slug, "created": True}


@app.get("/api/documents")
def list_documents(folder: Optional[str] = None):
    folder_slug = slugify_folder(folder) if folder else None
    return {"documents": rag.list_documents(folder_slug)}


@app.post("/api/upload", dependencies=[Depends(require_admin)])
async def upload_document(
    file: UploadFile = File(...),
    folder: str = Form(DEFAULT_FOLDER),
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Arquivo sem nome.")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato não suportado. Aceitos: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    folder_slug = slugify_folder(folder)
    folder_dir = DOCUMENTS_DIR / folder_slug
    folder_dir.mkdir(parents=True, exist_ok=True)

    safe_name = f"{uuid.uuid4().hex[:8]}_{Path(file.filename).name}"
    dest = folder_dir / safe_name

    size_bytes = 0
    with dest.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            size_bytes += len(chunk)
            if size_bytes > MAX_UPLOAD_MB * 1024 * 1024:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail=f"Arquivo excede {MAX_UPLOAD_MB} MB.")
            out.write(chunk)

    try:
        chunks_added = rag.index_document(dest, source_name=file.filename, folder=folder_slug)
    except Exception as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Falha ao indexar o documento: {exc}") from exc

    # Arquiva metadados no PostgreSQL (falha silenciosa para não bloquear o upload)
    try:
        article = Article(
            folder=folder_slug,
            filename=file.filename,
            stored_as=safe_name,
            file_size=size_bytes,
            file_type=suffix,
            chunks_indexed=chunks_added,
        )
        db.add(article)
        db.commit()
    except Exception as db_exc:
        print(f"[WARNING] Falha ao arquivar artigo no banco de dados: {db_exc}")
        try:
            db.rollback()
        except Exception:
            pass

    return {
        "filename": file.filename,
        "folder": folder_slug,
        "stored_as": safe_name,
        "chunks_indexed": chunks_added,
    }


@app.delete(
    "/api/folders/{folder}/documents/{source_name}",
    dependencies=[Depends(require_admin)],
)
def delete_document(folder: str, source_name: str):
    folder_slug = slugify_folder(folder)
    removed = rag.delete_document(folder_slug, source_name)
    if removed == 0:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")
    folder_dir = DOCUMENTS_DIR / folder_slug
    if folder_dir.exists():
        for path in folder_dir.glob(f"*_{source_name}"):
            path.unlink(missing_ok=True)
    return {"folder": folder_slug, "source": source_name, "chunks_removed": removed}


@app.delete("/api/folders/{folder}", dependencies=[Depends(require_admin)])
def delete_folder(folder: str):
    folder_slug = slugify_folder(folder)
    folder_dir = DOCUMENTS_DIR / folder_slug
    existed_on_disk = folder_dir.exists()

    removed = rag.delete_folder(folder_slug)

    if existed_on_disk:
        shutil.rmtree(folder_dir, ignore_errors=True)

    if removed == 0 and not existed_on_disk:
        raise HTTPException(status_code=404, detail="Pasta não encontrada.")
    return {"folder": folder_slug, "chunks_removed": removed}


def _validate_ask(payload: AskRequest):
    """Valida a pergunta e o escopo; devolve (question, folder_slug, source)."""
    question = (payload.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Pergunta vazia.")

    folders = rag.list_folders()
    if not folders:
        raise HTTPException(
            status_code=400,
            detail="Nenhum artigo indexado. Envie pelo menos um documento antes de perguntar.",
        )

    folder_slug = slugify_folder(payload.folder) if payload.folder else None
    if folder_slug and not any(f["folder"] == folder_slug for f in folders):
        raise HTTPException(status_code=404, detail=f"Pasta '{folder_slug}' não existe.")

    source = (payload.source or "").strip() or None
    return question, folder_slug, source


def _save_sources(sources: list) -> None:
    """Persiste, um registro por artigo distinto, as fontes usadas numa resposta.

    Best-effort: qualquer falha (banco indisponível, etc.) é apenas registrada
    no console e nunca interrompe a resposta ao usuário.
    """
    try:
        db = SessionLocal()
    except Exception as exc:
        print(f"[WARNING] Não foi possível abrir sessão do banco: {exc}")
        return

    try:
        grouped: dict = {}
        for s in sources:
            key = (s.get("folder"), s.get("source"))
            entry = grouped.setdefault(key, {"locations": [], "snippet": s.get("snippet", "")})
            loc = s.get("location")
            if loc and loc not in entry["locations"]:
                entry["locations"].append(loc)

        for (fld, art), info in grouped.items():
            db.add(
                QuestionSource(
                    folder=fld,
                    article=art,
                    locations=", ".join(info["locations"]),
                    snippet=info["snippet"],
                )
            )
        db.commit()
    except Exception as exc:
        print(f"[WARNING] Falha ao salvar fontes no banco: {exc}")
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


@app.post("/api/ask", response_model=AskResponse)
def ask(payload: AskRequest):
    question, folder_slug, source = _validate_ask(payload)
    try:
        result = rag.ask(question, folder=folder_slug, source=source)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Falha ao gerar resposta. Verifique se o Ollama está em execução "
                f"e se os modelos foram baixados. Detalhe: {exc}"
            ),
        ) from exc

    _save_sources(result["sources"])
    return result


@app.post("/api/ask/stream")
def ask_stream(payload: AskRequest):
    """Versão em streaming: emite NDJSON (uma linha JSON por evento).

    Eventos: {"type":"token","text":...} durante a geração e, ao final,
    {"type":"done","sources":[...],"scope":...}. Erros viram
    {"type":"error","detail":...}.
    """
    question, folder_slug, source = _validate_ask(payload)

    # A recuperação acontece antes do streaming para que falhas (ex.: Ollama
    # indisponível ao gerar embeddings) retornem um status HTTP adequado.
    try:
        docs = rag.retrieve(question, folder=folder_slug, source=source)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Falha ao recuperar trechos. Verifique se o Ollama está em "
                f"execução e se os modelos foram baixados. Detalhe: {exc}"
            ),
        ) from exc

    sources = rag._build_sources(docs)
    scope = rag._scope_label(folder_slug, source)

    def generate():
        try:
            for token in rag.stream_answer(question, docs):
                yield json.dumps({"type": "token", "text": token}, ensure_ascii=False) + "\n"
        except Exception as exc:
            yield json.dumps({"type": "error", "detail": str(exc)}, ensure_ascii=False) + "\n"
            return

        yield json.dumps(
            {"type": "done", "sources": sources, "scope": scope}, ensure_ascii=False
        ) + "\n"

        _save_sources(sources)

    return StreamingResponse(generate(), media_type="application/x-ndjson")


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
