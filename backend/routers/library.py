"""
Acervo de artigos: assuntos (pastas), artigos indexados, upload, leitura,
remoção e o arquivamento de metadados no PostgreSQL.
"""

import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from config import (
    DEFAULT_FOLDER,
    DOCUMENTS_DIR,
    MAX_UPLOAD_MB,
    SUPPORTED_EXTENSIONS,
    slugify_folder,
)
from database import get_db
from dependencies import get_rag, require_admin
from models import Article
from rag import RAGService
from schemas import CreateFolderRequest

router = APIRouter(prefix="/api", tags=["acervo"])


@router.get("/articles")
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


@router.get("/folders")
def list_folders(rag: RAGService = Depends(get_rag)):
    indexed = rag.list_folders()
    indexed_names = {f["folder"] for f in indexed}
    for path in DOCUMENTS_DIR.iterdir():
        if path.is_dir() and path.name not in indexed_names:
            indexed.append({"folder": path.name, "chunks": 0, "documents": 0})
    indexed.sort(key=lambda f: f["folder"])
    return {"folders": indexed}


@router.post("/folders", status_code=201, dependencies=[Depends(require_admin)])
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


@router.get("/documents")
def list_documents(folder: Optional[str] = None, rag: RAGService = Depends(get_rag)):
    folder_slug = slugify_folder(folder) if folder else None
    return {"documents": rag.list_documents(folder_slug)}


@router.get("/articles/{folder}/{source}/content")
def article_content(folder: str, source: str):
    """Devolve o texto de um artigo .md/.txt para leitura na interface.

    Aberto a qualquer perfil (Leitor pode ler). PDFs não são pré-visualizados
    como texto. O arquivo em disco pode ter sido salvo com o nome original
    (lote) ou com prefixo único (upload), então tentamos os dois.
    """
    suffix = Path(source).suffix.lower()
    if suffix not in {".md", ".txt"}:
        raise HTTPException(
            status_code=415,
            detail="Pré-visualização disponível apenas para arquivos .md e .txt.",
        )

    folder_dir = DOCUMENTS_DIR / slugify_folder(folder)
    path = folder_dir / source
    if not path.exists():
        matches = list(folder_dir.glob(f"*_{source}"))
        path = matches[0] if matches else None

    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")

    content = path.read_text(encoding="utf-8", errors="replace")
    return {"folder": slugify_folder(folder), "source": source, "content": content}


@router.post("/upload", dependencies=[Depends(require_admin)])
async def upload_document(
    file: UploadFile = File(...),
    folder: str = Form(DEFAULT_FOLDER),
    db: Session = Depends(get_db),
    rag: RAGService = Depends(get_rag),
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


@router.delete(
    "/folders/{folder}/documents/{source_name}",
    dependencies=[Depends(require_admin)],
)
def delete_document(folder: str, source_name: str, rag: RAGService = Depends(get_rag)):
    folder_slug = slugify_folder(folder)
    removed = rag.delete_document(folder_slug, source_name)
    if removed == 0:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")
    folder_dir = DOCUMENTS_DIR / folder_slug
    if folder_dir.exists():
        for path in folder_dir.glob(f"*_{source_name}"):
            path.unlink(missing_ok=True)
    return {"folder": folder_slug, "source": source_name, "chunks_removed": removed}


@router.delete("/folders/{folder}", dependencies=[Depends(require_admin)])
def delete_folder(folder: str, rag: RAGService = Depends(get_rag)):
    folder_slug = slugify_folder(folder)
    folder_dir = DOCUMENTS_DIR / folder_slug
    existed_on_disk = folder_dir.exists()

    removed = rag.delete_folder(folder_slug)

    if existed_on_disk:
        shutil.rmtree(folder_dir, ignore_errors=True)

    if removed == 0 and not existed_on_disk:
        raise HTTPException(status_code=404, detail="Pasta não encontrada.")
    return {"folder": folder_slug, "chunks_removed": removed}
