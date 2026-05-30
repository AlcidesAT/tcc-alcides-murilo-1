"""
API HTTP do Sistema Inteligente de Consulta a Artigos Científicos.

Expõe endpoints para upload e organização de artigos em pastas,
consulta em linguagem natural (opcionalmente restrita a uma pasta),
listagem e remoção de documentos e pastas, autenticação de usuários
e arquivamento de artigos no PostgreSQL, além de servir o front-end.
"""

import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import (
    BASE_DIR,
    DEFAULT_FOLDER,
    DOCUMENTS_DIR,
    MAX_UPLOAD_MB,
    SUPPORTED_EXTENSIONS,
    slugify_folder,
)
from rag_service import RAGService
from database import get_db, init_db
from models import User, Article
from auth import get_current_user, hash_password, verify_password, create_token


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
        print("[INFO] Banco de dados PostgreSQL inicializado.")
    except Exception as exc:
        print(f"[WARNING] Banco de dados PostgreSQL não disponível: {exc}")
        print("[WARNING] Autenticação e arquivamento desabilitados até que o BD esteja acessível.")
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


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@app.post("/api/auth/register", status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    try:
        name = (payload.name or "").strip()
        email = (payload.email or "").strip().lower()
        if not name or not email or not payload.password:
            raise HTTPException(status_code=400, detail="Nome, e-mail e senha são obrigatórios.")
        if len(payload.password) < 6:
            raise HTTPException(status_code=400, detail="Senha deve ter no mínimo 6 caracteres.")

        existing = db.query(User).filter(User.email == email).first()
        if existing:
            raise HTTPException(status_code=409, detail="E-mail já cadastrado.")

        user = User(name=name, email=email, password_hash=hash_password(payload.password))
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_token(user.id)
        return {
            "token": token,
            "user": {"id": str(user.id), "name": user.name, "email": user.email},
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Banco de dados indisponível: {exc}") from exc


@app.post("/api/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    try:
        email = (payload.email or "").strip().lower()
        user = db.query(User).filter(User.email == email).first()
        if not user or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail="E-mail ou senha incorretos.")
        token = create_token(user.id)
        return {
            "token": token,
            "user": {"id": str(user.id), "name": user.name, "email": user.email},
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Banco de dados indisponível: {exc}") from exc


@app.get("/api/auth/me")
def get_me(current_user: Optional[User] = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Não autenticado.")
    return {
        "id": str(current_user.id),
        "name": current_user.name,
        "email": current_user.email,
        "created_at": current_user.created_at.isoformat(),
    }


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
                    "user_id": str(a.user_id) if a.user_id else None,
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


@app.post("/api/folders", status_code=201)
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


@app.post("/api/upload")
async def upload_document(
    file: UploadFile = File(...),
    folder: str = Form(DEFAULT_FOLDER),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
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
            user_id=current_user.id if current_user else None,
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


@app.delete("/api/folders/{folder}/documents/{source_name}")
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


@app.delete("/api/folders/{folder}")
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


@app.post("/api/ask", response_model=AskResponse)
def ask(payload: AskRequest):
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

    return result


# ---------------------------------------------------------------------------
# Static files & frontend routes
# ---------------------------------------------------------------------------

FRONTEND_DIR = BASE_DIR / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    def root():
        return FileResponse(str(FRONTEND_DIR / "index.html"))

    @app.get("/login")
    def login_page():
        return FileResponse(str(FRONTEND_DIR / "login.html"))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
