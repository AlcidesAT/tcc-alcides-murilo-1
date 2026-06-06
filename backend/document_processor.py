"""
Carregamento e fragmentação de artigos científicos.

Aceita PDF, Markdown e texto simples, divide em chunks com sobreposição
e devolve documentos LangChain prontos para indexação.

Cada chunk recebe um localizador de origem:
  - PDF: número da página (1-based) em `loc_kind="page"`;
  - MD/TXT: número da linha onde o trecho começa em `loc_kind="line"`.
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
    suffix = path.suffix.lower()
    is_pdf = suffix == ".pdf"

    loader = _select_loader(path)
    raw_docs = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
        add_start_index=True,
    )
    chunks = splitter.split_documents(raw_docs)

    # Para MD/TXT (um único documento), o texto completo permite converter o
    # deslocamento de caractere (start_index) no número da linha do trecho.
    full_text = raw_docs[0].page_content if (not is_pdf and raw_docs) else ""

    for i, chunk in enumerate(chunks):
        chunk.metadata["source"] = source_name
        chunk.metadata["folder"] = folder
        chunk.metadata["chunk_index"] = i

        if is_pdf:
            page = chunk.metadata.get("page", 0) or 0
            chunk.metadata["loc_kind"] = "page"
            chunk.metadata["loc_value"] = int(page) + 1  # PyPDF é 0-based
        else:
            start = chunk.metadata.get("start_index", 0) or 0
            line = full_text[:start].count("\n") + 1
            chunk.metadata["loc_kind"] = "line"
            chunk.metadata["loc_value"] = line

        # Mantém `page` por compatibilidade (0 quando não se aplica).
        chunk.metadata.setdefault("page", chunk.metadata.get("page", 0))

    return chunks
