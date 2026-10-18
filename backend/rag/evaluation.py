"""
Avaliação automática da precisão das respostas.

Calcula, sem chamadas extras ao modelo, dois indicadores para cada resposta:

  - Fundamentação (groundedness): fração das frases da resposta cujos termos
    informativos aparecem nos trechos recuperados. Uma frase é "fundamentada"
    quando ao menos `EVAL_SENTENCE_SUPPORT` dos seus termos estão no contexto.
    Frases com termos que não existem em nenhum trecho (números, nomes,
    conclusões) indicam possível alucinação.
  - Cobertura da pergunta: fração dos termos da pergunta presentes nos trechos
    — mede se a recuperação trouxe material sobre o que foi perguntado.

Os termos são comparados por um radical simples (os primeiros caracteres da
palavra sem acento), para que "fertilizante" e "fertilizantes" ou "aplicação" e
"aplicada" contem como o mesmo termo.

As métricas são heurísticas, deterministas e explicáveis; servem como sinal de
confiança para o usuário e como medida comparável entre versões do sistema,
complementando a avaliação humana (nota de 1 a 5) registrada na interface.
"""

import re
from typing import Dict, List, Optional

from langchain_core.documents import Document

from config import (
    EVAL_LEVEL_HIGH,
    EVAL_LEVEL_MEDIUM,
    EVAL_MIN_SENTENCE_TERMS,
    EVAL_SENTENCE_SUPPORT,
)
from rag.lexical import stem, tokenize

# Termos de "metadiscurso" da resposta (referem-se ao próprio texto, não ao
# conteúdo dos artigos) e que não devem pesar contra a fundamentação.
_META_TERMS = {
    "trecho", "trechos", "fonte", "fontes", "contexto", "pasta", "resposta",
    "pergunta", "usuario", "informacao", "informacoes", "suficiente", "segundo",
    "acordo", "conforme", "citado", "citada", "mencionado", "mencionada",
}

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?;])\s+|\n+")


def _stems(text: str) -> List[str]:
    return [stem(t) for t in tokenize(text) if t not in _META_TERMS]


def _level(groundedness: Optional[float]) -> str:
    if groundedness is None:
        return "indefinido"
    if groundedness >= EVAL_LEVEL_HIGH:
        return "alta"
    if groundedness >= EVAL_LEVEL_MEDIUM:
        return "media"
    return "baixa"


def evaluate_answer(question: str, answer: str, docs: List[Document]) -> Dict:
    """Mede o quanto a resposta e a recuperação se apoiam nos trechos."""
    context = set()
    for d in docs:
        context.update(_stems(d.page_content))

    considered = supported = 0
    for sentence in _SENTENCE_SPLIT.split(answer or ""):
        stems = set(_stems(sentence))
        if len(stems) < EVAL_MIN_SENTENCE_TERMS:
            continue
        considered += 1
        if len(stems & context) / len(stems) >= EVAL_SENTENCE_SUPPORT:
            supported += 1

    groundedness = (supported / considered) if considered else None

    q_stems = set(_stems(question))
    coverage = (len(q_stems & context) / len(q_stems)) if q_stems else None

    return {
        "groundedness": round(groundedness, 3) if groundedness is not None else None,
        "question_coverage": round(coverage, 3) if coverage is not None else None,
        "sentences": considered,
        "supported_sentences": supported,
        "level": _level(groundedness),
    }
