"""
Carregamento e fragmentação de artigos científicos.

Aceita PDF, Markdown e texto simples, divide em chunks com sobreposição
e devolve documentos LangChain prontos para indexação.
"""

from pathlib import Path
from typing import List

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import CHUNK_OVERLAP, CHUNK_SIZE


def _select_loader(path: Path):
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return PyPDFLoader(str(path))
    if suffix in {".md", ".txt"}:
        return TextLoader(str(path), encoding="utf-8")
    raise ValueError(f"Formato não suportado: {suffix}")


def load_and_split(path: Path, source_name: str, folder: str) -> List[Document]:
    loader = _select_loader(path)
    raw_docs = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(raw_docs)

    for chunk in chunks:
        chunk.metadata["source"] = source_name
        chunk.metadata["folder"] = folder
        chunk.metadata.setdefault("page", chunk.metadata.get("page", 0))

    return chunks
