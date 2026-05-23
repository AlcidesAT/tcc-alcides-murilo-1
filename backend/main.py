"""
API HTTP do Sistema Inteligente de Consulta a Artigos Científicos.

Expõe endpoints para upload e organização de artigos em pastas,
consulta em linguagem natural (opcionalmente restrita a uma pasta),
listagem e remoção de documentos e pastas, além de servir o front-end.
"""

import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import (
    BASE_DIR,
    DEFAULT_FOLDER,
    DOCUMENTS_DIR,
    MAX_UPLOAD_MB,
    SUPPORTED_EXTENSIONS,
    slugify_folder,
)
from rag_service import RAGService


app = FastAPI(
    title="Consulta Inteligente a Artigos Científicos",
    description="Sistema RAG para consulta em linguagem natural a artigos científicos.",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

rag = RAGService()


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
        raise HTTPException(
            status_code=409,
            detail=f"A pasta '{folder_slug}' já existe.",
        )
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
                raise HTTPException(
                    status_code=413,
                    detail=f"Arquivo excede {MAX_UPLOAD_MB} MB.",
                )
            out.write(chunk)

    try:
        chunks_added = rag.index_document(
            dest, source_name=file.filename, folder=folder_slug
        )
    except Exception as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(
            status_code=500,
            detail=f"Falha ao indexar o documento: {exc}",
        ) from exc

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
        raise HTTPException(
            status_code=404,
            detail=f"Pasta '{folder_slug}' não existe.",
        )

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


FRONTEND_DIR = BASE_DIR / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    def root():
        return FileResponse(str(FRONTEND_DIR / "index.html"))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
