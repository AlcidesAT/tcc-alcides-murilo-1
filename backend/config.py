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
# Modelo leve (~1,3 GB) para reduzir uso de RAM/pagefile. Para respostas mais
# elaboradas, troque por "llama3.2" (3B) ou um modelo maior, se houver memória.
LLM_MODEL = "llama3.2:1b"
EMBEDDING_MODEL = "nomic-embed-text"

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# Recuperação:
#  - RETRIEVAL_K: quantos trechos são enviados ao modelo (mais = resposta mais completa).
#  - MMR_FETCH_K: quantos candidatos a busca examina antes de escolher os K finais.
#  - MMR_LAMBDA: 0 = máxima diversidade, 1 = máxima relevância. 0.7 prioriza a
#    relevância (mantendo alguma diversidade), o que melhora perguntas cujo
#    conteúdo está concentrado em um único artigo, mesmo sem filtrar por assunto.
RETRIEVAL_K = 8
MMR_FETCH_K = 40
MMR_LAMBDA = 0.7

# Referências exibidas ao usuário (trilha lateral):
#  - REFERENCES_MAX: nº máximo de artigos distintos mostrados.
#  - REFERENCES_MIN_RATIO: corte relativo — mantém apenas artigos cuja
#    relevância (BM25 no nível do artigo) seja >= esta fração do melhor. Assim,
#    quando só um artigo trata do tema, só ele aparece (sem completar a lista
#    com artigos pouco relacionados).
REFERENCES_MAX = 5
REFERENCES_MIN_RATIO = 0.45

COLLECTION_NAME = "artigos_cientificos"

SUPPORTED_EXTENSIONS = {".pdf", ".md", ".txt"}
MAX_UPLOAD_MB = 50

DEFAULT_FOLDER = "geral"
MAX_FOLDER_NAME_LEN = 50

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/tcc_rag",
)

# Perfis de acesso. O sistema prevê dois perfis: Leitor (apenas consulta) e
# Administrador (envio, organização e indexação de artigos). O perfil Leitor é
# o padrão; para virar Administrador, o usuário informa esta senha, validada
# no backend. Defina ADMIN_PASSWORD no .env em produção.
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")


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
