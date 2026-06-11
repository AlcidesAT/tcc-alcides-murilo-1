"""
Configurações do sistema RAG.

Centraliza parâmetros do modelo, caminhos de armazenamento e
hiperparâmetros do pipeline de recuperação.
"""

import os
import re
import unicodedata
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # python-dotenv é opcional; segue com as variáveis do ambiente
    pass


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DOCUMENTS_DIR = DATA_DIR / "documents"
VECTORSTORE_DIR = DATA_DIR / "vectorstore"

DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
VECTORSTORE_DIR.mkdir(parents=True, exist_ok=True)

OLLAMA_BASE_URL = "http://localhost:11434"
LLM_MODEL = "llama3.2:1b"
EMBEDDING_MODEL = "nomic-embed-text"

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# Recuperação:
#  - RETRIEVAL_K: quantos trechos são enviados ao modelo (mais = resposta mais completa).
#  - MMR_FETCH_K: quantos candidatos a busca examina antes de escolher os K finais.
#  - MMR_LAMBDA: 0 = máxima diversidade, 1 = máxima relevância (0.5 equilibra os dois).
RETRIEVAL_K = 8
MMR_FETCH_K = 24
MMR_LAMBDA = 0.5

COLLECTION_NAME = "artigos_cientificos"

SUPPORTED_EXTENSIONS = {".pdf", ".md", ".txt"}
MAX_UPLOAD_MB = 50

DEFAULT_FOLDER = "geral"
MAX_FOLDER_NAME_LEN = 50

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/artigos_db",
)


def slugify_folder(name: str | None) -> str:
    """Converte um nome livre em um slug seguro para sistema de arquivos.

    Remove acentos, converte para minúsculas, troca não-alfanuméricos por hífen.
    Devolve DEFAULT_FOLDER caso o resultado seja vazio.
    """
    if not name:
        return DEFAULT_FOLDER
    decomposed = unicodedata.normalize("NFKD", name)
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii")
    s = ascii_only.strip().lower()
    s = re.sub(r"[^a-z0-9_-]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    s = s[:MAX_FOLDER_NAME_LEN]
    return s or DEFAULT_FOLDER
