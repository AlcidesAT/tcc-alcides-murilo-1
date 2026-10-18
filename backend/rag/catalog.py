"""
Perguntas sobre o acervo.

Perguntas como "quais artigos da base falam de tecnologia?" ou "me diga os
assuntos relacionados à saúde" não pedem o conteúdo de um trecho, e sim a
LISTA de artigos — que o modelo não enxerga quando recebe só os trechos
recuperados (e que o llama3.2:1b não consegue ler de forma confiável nem
quando a lista vai no prompt). Por isso essas perguntas são respondidas
diretamente a partir do índice, sem o LLM:

  1. o tema é o que sobra da pergunta sem as palavras de enunciado
     ("me diga assuntos da base relacionado à tecnologia" -> "tecnologia");
  2. entram os artigos cujo título ou assunto contém o tema (por radical:
     "tecnologia" casa com "ciencias-exatas-e-tecnologicas");
  3. e, à parte, os artigos cujo conteúdo trata do tema (BM25 no nível do
     artigo, com o mesmo corte relativo das referências).
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from config import FOLDER_DISPLAY_NAMES, REFERENCES_MIN_RATIO
from rag.lexical import STOPWORDS, LexicalIndex, stem, tokenize, words
from rag.retrieval import ref_entry

# Substantivos que designam conjuntos de artigos (no plural, para não confundir
# com "o artigo" de que se está falando).
_CORPUS_NOUNS = {
    "artigos", "assuntos", "temas", "trabalhos", "estudos", "pesquisas",
    "publicacoes", "documentos",
}
# Pedidos de listagem ou de existência.
_LISTING = {
    "quais", "que", "liste", "listar", "lista", "diga", "cite", "mostre",
    "existem", "existe", "tem", "temos", "ha", "possui", "quantos", "quantas",
}
# "da base", "na base", "do acervo"…: referência explícita ao acervo.
_BASE_PREFIX = {"da", "na", "nessa", "nesta", "dessa", "desta", "a"}
_FILLER = {"o", "a", "os", "as", "me", "sao", "e", "todos", "todas", "outros", "mais"}

_NON_TOPIC = STOPWORDS | _CORPUS_NOUNS | _LISTING | {
    "base", "acervo", "sistema", "aqui", "disponiveis", "disponivel", "falam",
    "sobre", "area", "areas", "tema", "relacionam", "envolvem", "tratando",
    # Verbos de pesquisa ("quais estudos avaliaram a alface?"): não são o tema.
    "avaliaram", "avaliam", "avalia", "estudaram", "estudam", "analisaram",
    "analisam", "investigaram", "investigam", "testaram", "usaram", "utilizaram",
}

CONTENT_MAX = 5


def is_catalog_question(question: str) -> bool:
    """A pergunta pede a lista de artigos/assuntos do acervo?"""
    ws = words(question)
    if "acervo" in ws:
        return True
    if any(a in _BASE_PREFIX and b == "base" for a, b in zip(ws, ws[1:])) and set(ws) & _LISTING:
        return True
    # Pedido de listagem seguido de perto por um substantivo de acervo,
    # pulando palavras de ligação: "quais (são os) artigos", "me diga assuntos".
    for i, w in enumerate(ws):
        if w not in _LISTING:
            continue
        for nxt in ws[i + 1 : i + 4]:
            if nxt in _CORPUS_NOUNS:
                return True
            if nxt not in _FILLER:
                break
    return False


def folder_label(slug: str) -> str:
    return FOLDER_DISPLAY_NAMES.get(slug) or slug.replace("-", " ").capitalize()


def _topic(question: str) -> Tuple[str, set]:
    """Tema da pergunta: as palavras (com acento, para exibir) e seus radicais."""
    shown, stems = [], set()
    for raw in re.findall(r"\w+", question):
        norm = words(raw)
        if not norm or norm[0] in _NON_TOPIC or len(norm[0]) < 3:
            continue
        shown.append(raw)
        stems.add(stem(norm[0]))
    return " ".join(shown), stems


def answer_catalog(
    question: str,
    documents: List[Dict],
    lexical: LexicalIndex,
    folder: Optional[str] = None,
) -> Tuple[str, List[Dict]]:
    """Monta a resposta (Markdown) e as referências para uma pergunta de acervo."""
    topic, topic_stems = _topic(question)
    docs = [d for d in documents if not folder or d["folder"] == folder]

    if not topic_stems:
        return _overview(docs, folder), []

    # 1) Tema no título ou no nome do assunto. Temas de até duas palavras
    #    ("saúde mental") precisam aparecer inteiros; maiores, pela metade.
    need = len(topic_stems) if len(topic_stems) <= 2 else -(-len(topic_stems) // 2)
    by_title = []
    for d in docs:
        title_stems = {stem(t) for t in tokenize(f"{Path(d['source']).stem} {d['folder']}")}
        hits = len(topic_stems & title_stems)
        if hits >= need:
            by_title.append((hits, d))
    by_title.sort(key=lambda x: (-x[0], x[1]["folder"], x[1]["source"]))
    listed = {(d["folder"], d["source"]) for _, d in by_title}

    # 2) Tema no conteúdo (artigos ainda não listados).
    terms = [t for t in tokenize(question) if t not in _NON_TOPIC]
    ranked = lexical.rank_articles(terms, folder)
    by_content = []
    if ranked:
        cutoff = ranked[0][0] * REFERENCES_MIN_RATIO
        for score, art in ranked:
            if score < cutoff or len(by_content) >= CONTENT_MAX:
                break
            meta = art["chunks"][0]["meta"]
            key = (meta.get("folder"), meta.get("source"))
            if key not in listed:
                by_content.append(art)

    if not by_title and not by_content:
        return (
            f"Não encontrei artigos do acervo sobre “{topic}”.\n\n" + _overview(docs, folder),
            [],
        )

    lines = []
    total = len(by_title) + len(by_content)
    lines.append(
        f"Encontrei {total} artigos no acervo relacionados a “{topic}”:"
        if total != 1
        else f"Encontrei 1 artigo no acervo relacionado a “{topic}”:"
    )
    sources = []

    groups: Dict[str, List[str]] = {}
    for _, d in by_title:
        groups.setdefault(d["folder"], []).append(Path(d["source"]).stem)
        best = _first_chunk(lexical, d["folder"], d["source"])
        if best:
            sources.append(ref_entry(best["text"], best["meta"]))
    for f in sorted(groups):
        lines.append(f"\n**{folder_label(f)}**")
        lines.extend(f"- {t}" for t in groups[f])

    if by_content:
        lines.append("\n**Também mencionam o tema no conteúdo**")
        for art in by_content:
            best = max(art["chunks"], key=lambda ch: lexical.score_chunk(ch, terms))
            meta = best["meta"]
            lines.append(f"- {Path(meta.get('source', '?')).stem} ({folder_label(meta.get('folder', '?'))})")
            sources.append(ref_entry(best["text"], meta))

    lines.append("\nPergunte sobre qualquer um deles para ver os detalhes.")
    return "\n".join(lines), sources


def _first_chunk(lexical: LexicalIndex, folder: str, source: str) -> Optional[Dict]:
    for ch in lexical.chunks(folder, source):
        return ch
    return None


def _overview(docs: List[Dict], folder: Optional[str]) -> str:
    """Resumo do acervo por assunto (quando a pergunta não indica um tema)."""
    counts: Dict[str, int] = {}
    for d in docs:
        counts[d["folder"]] = counts.get(d["folder"], 0) + 1
    if not counts:
        return "O acervo ainda não tem artigos indexados."
    lines = ["O acervo tem os seguintes assuntos:"]
    lines.extend(
        f"- **{folder_label(f)}** — {n} {'artigo' if n == 1 else 'artigos'}"
        for f, n in sorted(counts.items())
    )
    return "\n".join(lines)
