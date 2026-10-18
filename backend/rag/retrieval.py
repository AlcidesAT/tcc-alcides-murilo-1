"""
Módulo de recuperação.

Busca híbrida (semântica + palavra-chave) dos trechos enviados ao modelo e
seleção dos artigos exibidos como referências ao usuário.
"""

from pathlib import Path
from typing import Dict, List, Optional, Union

from langchain_core.documents import Document

from config import (
    MMR_FETCH_K,
    MMR_LAMBDA,
    REFERENCES_MAX,
    REFERENCES_MIN_RATIO,
    RETRIEVAL_K,
)
from rag.lexical import LexicalIndex, tokenize


def location_label(md: dict) -> str:
    """Rótulo legível da origem do trecho: 'p. N' (PDF) ou 'linha N' (MD/TXT)."""
    kind = md.get("loc_kind")
    value = md.get("loc_value")
    if kind == "page" and value:
        return f"p. {value}"
    if kind == "line" and value:
        return f"linha {value}"
    # Compatibilidade com documentos indexados antes deste campo existir.
    page = md.get("page")
    if page:
        return f"p. {page}"
    return "trecho"


def scope_label(folder: Optional[str], source: Optional[str]) -> str:
    if folder and source:
        return f"{folder} / {source}"
    if folder:
        return folder
    return "todas"


def ref_entry(text: str, meta: dict) -> Dict:
    source = meta.get("source", "?")
    return {
        "folder": meta.get("folder", "?"),
        "source": source,
        "location": location_label(meta),
        "snippet": text[:240].strip().replace("\n", " ") + "…",
        "file_type": Path(source).suffix.lower(),
    }


def _doc_key(meta: dict) -> tuple:
    """Identificador estável de um chunk (para deduplicar na fusão)."""
    return (
        meta.get("folder"),
        meta.get("source"),
        meta.get("chunk_index"),
        meta.get("loc_value"),
    )


def _fuse(ranked_lists: List[List[Document]], k: int = 60) -> List[Document]:
    """Reciprocal Rank Fusion: combina várias listas ordenadas em uma só.

    Cada documento soma 1/(k + posição) de cada lista em que aparece; assim,
    trechos bem ranqueados na busca semântica E na lexical sobem ao topo.
    """
    scores: Dict[tuple, float] = {}
    docs: Dict[tuple, Document] = {}
    for ranked in ranked_lists:
        for rank, doc in enumerate(ranked):
            key = _doc_key(doc.metadata)
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            docs.setdefault(key, doc)
    ordered = sorted(scores.keys(), key=lambda key: scores[key], reverse=True)
    return [docs[key] for key in ordered]


class HybridRetriever:
    """Combina a busca semântica (MMR) com a busca por palavra-chave (BM25)."""

    def __init__(self, vectorstore, lexical: LexicalIndex) -> None:
        self.vectorstore = vectorstore
        self.lexical = lexical

    def _vector_search(
        self,
        query: str,
        folder: Optional[str],
        source: Optional[str],
    ) -> List[Document]:
        """Busca semântica (MMR) — relevância + diversidade no espaço vetorial."""
        search_kwargs = {
            "k": RETRIEVAL_K,
            "fetch_k": MMR_FETCH_K,
            "lambda_mult": MMR_LAMBDA,
        }
        filters = []
        if folder:
            filters.append({"folder": folder})
        if source:
            filters.append({"source": source})
        if len(filters) == 1:
            search_kwargs["filter"] = filters[0]
        elif len(filters) > 1:
            search_kwargs["filter"] = {"$and": filters}

        retriever = self.vectorstore.as_retriever(
            search_type="mmr", search_kwargs=search_kwargs
        )
        return retriever.invoke(query)

    def _keyword_search(
        self,
        query: str,
        folder: Optional[str],
        source: Optional[str],
    ) -> List[Document]:
        """Garante que termos literais da pergunta (ex.: a sigla "SUS") recuperem
        os trechos onde aparecem, mesmo quando a busca semântica não os destaca."""
        hits = self.lexical.search_chunks(tokenize(query), folder, source, k=RETRIEVAL_K)
        return [Document(page_content=ch["text"], metadata=ch["meta"]) for _, ch in hits]

    def retrieve(
        self,
        query: Union[str, List[str]],
        folder: Optional[str] = None,
        source: Optional[str] = None,
    ) -> List[Document]:
        """Recupera os trechos mais relevantes via **busca híbrida**.

        Funde a busca semântica e a lexical por Reciprocal Rank Fusion. Isso
        cobre tanto perguntas conceituais quanto termos/siglas literais (ex.:
        "SUS"), percorrendo todos os artigos. Restringível a pasta/artigo.

        Aceita várias consultas (memória de pergunta: reescrita + expansão);
        as listas de todas elas entram na mesma fusão.
        """
        queries = [query] if isinstance(query, str) else list(query)
        ranked = []
        for q in queries:
            ranked.append(self._vector_search(q, folder, source))
            keyword_docs = self._keyword_search(q, folder, source)
            if keyword_docs:
                ranked.append(keyword_docs)

        if len(ranked) == 1:
            return ranked[0][:RETRIEVAL_K]
        return _fuse(ranked)[:RETRIEVAL_K]

    def build_references(
        self,
        query: str,
        context_docs: List[Document],
        folder: Optional[str] = None,
        source: Optional[str] = None,
    ) -> List[Dict]:
        """Seleciona os ARTIGOS mais relacionados ao tema para exibir ao usuário.

        Diferente do contexto enviado ao modelo (vários trechos), aqui a unidade
        é o artigo: pontua cada artigo inteiro por BM25 contra a pergunta, mantém
        só os acima de um corte relativo ao melhor (`REFERENCES_MIN_RATIO`) e
        limita a `REFERENCES_MAX`. Evita repetir o mesmo artigo e não completa a
        lista com artigos pouco relevantes. Sem casamento de termos (pergunta
        genérica), recai sobre os artigos distintos da busca semântica.
        """
        terms = tokenize(query)
        scored = self.lexical.rank_articles(terms, folder, source)
        if scored:
            cutoff = scored[0][0] * REFERENCES_MIN_RATIO
            refs = []
            for s, art in scored:
                if s < cutoff or len(refs) >= REFERENCES_MAX:
                    break
                # Melhor trecho do artigo para o snippet/localização.
                best = max(art["chunks"], key=lambda ch: self.lexical.score_chunk(ch, terms))
                refs.append(ref_entry(best["text"], best["meta"]))
            return refs

        # Fallback: artigos distintos da busca semântica, na ordem recuperada.
        refs, seen = [], set()
        for d in context_docs:
            key = (d.metadata.get("folder"), d.metadata.get("source"))
            if key in seen:
                continue
            seen.add(key)
            refs.append(ref_entry(d.page_content, d.metadata))
            if len(refs) >= REFERENCES_MAX:
                break
        return refs
