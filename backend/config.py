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
EVALUATION_DIR = DATA_DIR / "evaluation"  # conjunto de perguntas do benchmark

DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
VECTORSTORE_DIR.mkdir(parents=True, exist_ok=True)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
# Modelo leve (~1,3 GB) para reduzir uso de RAM/pagefile. Para respostas mais
# elaboradas, troque por "llama3.2" (3B) ou um modelo maior, se houver memória.
# Pode ser sobrescrito no .env (LLM_MODEL=...), o que facilita comparar modelos
# na avaliação de precisão sem alterar o código.
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2:1b")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")

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

# Memória de pergunta (conversa):
#  - MEMORY_MAX_TURNS: quantos pares pergunta/resposta anteriores são lembrados.
#  - MEMORY_ANSWER_CHARS: tamanho máximo de cada resposta anterior levada ao
#    modelo (as respostas são resumidas por corte para não estourar o contexto).
MEMORY_MAX_TURNS = 4
MEMORY_ANSWER_CHARS = 600

# Avaliação automática da precisão (fundamentação da resposta nos trechos):
#  - EVAL_SENTENCE_SUPPORT: fração mínima dos termos de uma frase da resposta
#    que precisa aparecer nos trechos recuperados para a frase ser "fundamentada".
#  - EVAL_MIN_SENTENCE_TERMS: frases com menos termos informativos são ignoradas
#    (títulos, saudações, "Resposta:"...).
#  - EVAL_LEVEL_HIGH / EVAL_LEVEL_MEDIUM: cortes da fundamentação para os níveis
#    de confiança exibidos ao usuário (alta / média / baixa).
EVAL_SENTENCE_SUPPORT = 0.6
EVAL_MIN_SENTENCE_TERMS = 3
EVAL_LEVEL_HIGH = 0.75
EVAL_LEVEL_MEDIUM = 0.5

COLLECTION_NAME = "artigos_cientificos"

SUPPORTED_EXTENSIONS = {".pdf", ".md", ".txt"}
MAX_UPLOAD_MB = 50

DEFAULT_FOLDER = "geral"

# Nomes de exibição dos assuntos (mesmos de frontend/js/folders.js), usados nas
# respostas sobre o acervo.
FOLDER_DISPLAY_NAMES = {
    "ciencia-juridica": "Ciência Jurídica",
    "ciencias-agrarias": "Ciências Agrárias",
    "ciencias-da-educacao": "Ciências da Educação",
    "ciencias-da-vida-e-saude": "Ciências da Vida e Saúde",
    "ciencias-exatas-e-tecnologicas": "Ciências Exatas e Tecnológicas",
    "ciencias-sociais": "Ciências Sociais",
    "geral": "Geral",
}
MAX_FOLDER_NAME_LEN = 50

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/tcc_rag",
)

# Perfis de acesso:
#  - Leitor (padrão, sem login): apenas consulta; nada é registrado.
#  - Participante (login da turma): consulta + avaliação. Usado por todos nos
#    testes com usuários; cada login abre uma sessão anônima e as perguntas,
#    respostas, notas e o questionário vão para o banco de registro.
#  - Administrador: envio/gestão de artigos e acesso aos dados coletados.
# As senhas ficam SÓ no .env (fora do Git). Não há senha padrão no código:
# sem ADMIN_PASSWORD / PARTICIPANT_PASSWORD definida, aquele login fica
# desativado em vez de aceitar uma senha conhecida.
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
PARTICIPANT_USER = os.getenv("PARTICIPANT_USER", "turma")
PARTICIPANT_PASSWORD = os.getenv("PARTICIPANT_PASSWORD", "")

# Questionário de avaliação do sistema (afirmações de 1 a 5 estrelas).
SURVEY_FILE = EVALUATION_DIR / "questionario.json"


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


# O upload pelo site grava o arquivo com um prefixo único ("1a2b3c4d_Nome.pdf"),
# mas o artigo fica no índice com o nome original ("Nome.pdf"). Os artigos
# colocados direto na pasta (lote) ficam com o nome original nos dois lugares.
UPLOAD_PREFIX = re.compile(r"^[0-9a-f]{8}_")


def original_filename(stored_name: str) -> str:
    """Nome do artigo no índice a partir do nome do arquivo em disco."""
    return UPLOAD_PREFIX.sub("", stored_name, count=1)


def article_files(folder_dir: Path, source_name: str) -> list[Path]:
    """Arquivos em disco de um artigo indexado (com ou sem o prefixo do upload)."""
    if not folder_dir.is_dir():
        return []
    return [
        p
        for p in sorted(folder_dir.iterdir())
        if p.is_file() and original_filename(p.name) == source_name
    ]
