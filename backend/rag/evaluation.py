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
from pathlib import Path
from typing import Dict, List, Optional

from langchain_core.documents import Document

from config import (
    EVAL_LEVEL_HIGH,
    EVAL_LEVEL_MEDIUM,
    EVAL_MIN_SENTENCE_TERMS,
    EVAL_SENTENCE_SUPPORT,
    PASSAGE_MAX_CHARS,
    PASSAGE_MIN_CHARS,
    PASSAGE_MIN_SUPPORT,
    PASSAGES_MAX,
)
from rag.lexical import stem, tokenize
from rag.retrieval import location_label

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


def _passage(sentence: str, doc: Document) -> Dict:
    meta = doc.metadata
    source = meta.get("source", "?")
    # Tira as marcas do Markdown e o cabeçalho "ARTIGO" dos arquivos convertidos.
    quote = " ".join(re.sub(r"[*#]+|\bARTIGO\b", " ", sentence).split())
    if len(quote) > PASSAGE_MAX_CHARS:
        quote = quote[:PASSAGE_MAX_CHARS].rsplit(" ", 1)[0] + "…"
    return {
        "folder": meta.get("folder", "?"),
        "source": source,
        "location": location_label(meta),
        "file_type": Path(source).suffix.lower(),
        "quote": quote,
    }


def trace_passages(answer: str, docs: List[Document]) -> List[Dict]:
    """Liga as frases da resposta às passagens dos artigos que mais se parecem.

    Não usa o modelo: compara os termos de cada frase com as frases dos trechos
    que ele recebeu, então a passagem existe de verdade no artigo, ao contrário
    de uma citação escrita pelo próprio modelo. Mostra de onde a informação pode
    ter vindo, não prova que a frase está correta. Frases sem passagem parecida
    (ex.: conhecimento geral do modelo) ficam de fora.
    """
    candidates = []
    for doc in docs:
        for sentence in _SENTENCE_SPLIT.split(" ".join(doc.page_content.split())):
            stems = set(_stems(sentence))
            is_table = "<br>" in sentence or sentence.count("|") >= 2
            if len(sentence) >= PASSAGE_MIN_CHARS and stems and not is_table:
                candidates.append((sentence, stems, doc))
    if not candidates:
        return []

    matches: Dict[str, Dict] = {}  # passagem -> melhor frase da resposta
    for position, line in enumerate(_SENTENCE_SPLIT.split(answer or "")):
        terms = set(_stems(line))
        if len(terms) < EVAL_MIN_SENTENCE_TERMS:
            continue
        sentence, stems, doc = max(candidates, key=lambda c: len(terms & c[1]))
        support = len(terms & stems) / len(terms)
        if support < PASSAGE_MIN_SUPPORT:
            continue
        match = matches.setdefault(sentence, {"support": 0.0, "position": position, "doc": doc})
        match["support"] = max(match["support"], support)

    best = sorted(matches.items(), key=lambda m: m[1]["support"], reverse=True)[:PASSAGES_MAX]
    best.sort(key=lambda m: m[1]["position"])
    return [_passage(sentence, match["doc"]) for sentence, match in best]


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
