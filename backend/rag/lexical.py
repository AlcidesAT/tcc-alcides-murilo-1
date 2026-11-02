"""
Busca por palavra-chave (BM25).

Concentra a tokenização e o índice léxico usados em três pontos do sistema:
na busca híbrida (trechos), na escolha das referências (artigos) e na
avaliação automática das respostas. Antes, o cálculo do BM25 estava repetido
em cada um desses lugares; agora há uma única implementação.
"""

import math
import re
import threading
import unicodedata
from collections import Counter
from typing import Dict, Iterable, List, Optional, Tuple


# Palavras muito comuns em português, ignoradas na busca por palavra-chave para
# não diluir o sinal dos termos realmente informativos (ex.: "SUS", "biópsia").
# Inclui também verbos/substantivos "de pergunta" (aborda, fala, trata, artigo…)
# que aparecem em muitos textos e não dizem respeito ao tema consultado.
STOPWORDS = {
    "a", "o", "as", "os", "um", "uma", "uns", "umas", "de", "do", "da", "dos",
    "das", "no", "na", "nos", "nas", "em", "por", "para", "com", "sem", "sob",
    "e", "ou", "que", "qual", "quais", "quando", "como", "onde", "porque",
    "se", "ao", "aos", "à", "às", "the", "is", "of", "sobre", "entre", "ser",
    "sua", "seu", "suas", "seus", "isso", "este", "esta", "esse", "essa",
    "qual", "me", "minha", "meu", "ele", "ela", "foi", "são", "tem", "há",
    "no", "nos", "do", "os", "pelo", "pela", "isto", "aquele", "aquela",
    # Verbos e substantivos genéricos de enunciado (não indicam o tema):
    "artigo", "artigos", "texto", "textos", "questao", "questoes", "assunto",
    "aborda", "abordam", "abordar", "fala", "falam", "falar", "trata", "tratam",
    "tratar", "diz", "dizem", "mostra", "mostram", "apresenta", "apresentam",
    "explica", "explicam", "conta", "contam", "descreve", "descrevem",
    "qual", "quais", "fazer", "faz", "sao", "estao", "esta",
    # Pedidos sobre o próprio acervo ("me diga os assuntos relacionados a…"):
    "diga", "liste", "listar", "cite", "assuntos", "acervo",
    "relacionado", "relacionados", "relacionada", "relacionadas",
}

K1, B = 1.5, 0.75

# Radical simples por corte: "fertilizante"/"fertilizantes" -> "fertil".
STEM_LEN = 6


def words(text: str) -> List[str]:
    """Todas as palavras do texto, sem acentos e em minúsculas."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    return re.findall(r"[a-z0-9]+", text)


def tokenize(text: str) -> List[str]:
    """Normaliza para minúsculas, remove acentos e separa em termos úteis."""
    return [t for t in words(text) if len(t) >= 2 and t not in STOPWORDS]


def stem(token: str) -> str:
    return token[:STEM_LEN]


def bm25(
    tf: Counter,
    length: int,
    terms: Iterable[str],
    idf: Dict[str, float],
    avgdl: float,
) -> float:
    """Score BM25 de um documento (trecho ou artigo) para os termos da consulta."""
    avgdl = avgdl or 1.0
    score = 0.0
    for t in terms:
        f = tf.get(t, 0)
        if not f:
            continue
        denom = f + K1 * (1 - B + B * length / avgdl)
        score += idf.get(t, 0.0) * (f * (K1 + 1)) / denom
    return score


def _idf(df: Counter, n: int) -> Dict[str, float]:
    return {term: math.log(1 + (n - freq + 0.5) / (freq + 0.5)) for term, freq in df.items()}


class LexicalIndex:
    """Índice BM25 em memória sobre todos os trechos do acervo.

    É construído sob demanda a partir do vector store e só é refeito quando a
    quantidade de trechos muda (upload/remoção), mantendo o custo desprezível
    entre perguntas. Um lock evita reconstruções simultâneas, já que o FastAPI
    atende requisições em várias threads.
    """

    def __init__(self, vectorstore) -> None:
        self._vectorstore = vectorstore
        self._lock = threading.Lock()
        self._chunks: List[Dict] = []
        self._idf: Dict[str, float] = {}
        self._avgdl: float = 0.0
        self._count: int = -1
        self._articles: Dict[tuple, Dict] = {}  # estatísticas por escopo
        self._stem_idf: Dict[str, float] = {}

    def invalidate(self) -> None:
        """Força a reconstrução na próxima consulta.

        A contagem de trechos não muda quando um artigo é substituído por outro
        do mesmo tamanho; por isso o próprio processo avisa após cada alteração.
        """
        self._count = -1

    def refresh(self) -> None:
        count = self._vectorstore._collection.count()
        if self._count == count:
            return
        with self._lock:
            if self._count == count:
                return

            raw = self._vectorstore.get(include=["documents", "metadatas"])
            chunks = []
            df: Counter = Counter()
            stem_df: Counter = Counter()
            total_len = 0
            for text, meta in zip(raw.get("documents") or [], raw.get("metadatas") or []):
                tokens = tokenize(text)
                tf = Counter(tokens)
                stems = {stem(t) for t in tf}
                chunks.append({"text": text, "meta": meta or {}, "tf": tf, "len": len(tokens), "stems": stems})
                total_len += len(tokens)
                df.update(tf.keys())
                stem_df.update(stems)

            n = len(chunks) or 1
            self._chunks = chunks
            self._idf = _idf(df, n)
            self._stem_idf = _idf(stem_df, n)
            self._avgdl = total_len / n
            self._articles = {}
            self._count = count

    def folders(self) -> set:
        """Assuntos com trechos indexados."""
        self.refresh()
        return {ch["meta"].get("folder") for ch in self._chunks}

    def _scoped(self, folder: Optional[str], source: Optional[str]) -> Iterable[Dict]:
        for ch in self._chunks:
            meta = ch["meta"]
            if folder and meta.get("folder") != folder:
                continue
            if source and meta.get("source") != source:
                continue
            yield ch

    def chunks(self, folder: Optional[str] = None, source: Optional[str] = None) -> Iterable[Dict]:
        """Trechos do acervo (na ordem de indexação), restritos ao escopo."""
        self.refresh()
        return self._scoped(folder, source)

    def score_chunk(self, chunk: Dict, terms: List[str]) -> float:
        return bm25(chunk["tf"], chunk["len"], terms, self._idf, self._avgdl)

    def search_chunks(
        self,
        terms: List[str],
        folder: Optional[str] = None,
        source: Optional[str] = None,
        k: int = 8,
    ) -> List[Tuple[float, Dict]]:
        """Trechos com maior BM25 para os termos, restritos ao escopo."""
        if not terms:
            return []
        self.refresh()
        scored = []
        for ch in self._scoped(folder, source):
            s = self.score_chunk(ch, terms)
            if s > 0:
                scored.append((s, ch))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:k]

    def term_coverage(self, terms: List[str]) -> float:
        """Maior fração da pergunta reunida em um único trecho (de 0 a 1).

        Cada termo pesa pela raridade: "milho" conta mais que "melhor", e um
        termo ausente do acervo pesa o máximo. Usa radicais, como a avaliação.
        """
        self.refresh()
        absent = _idf(Counter({"": 0}), len(self._chunks) or 1)[""]
        weights = {s: self._stem_idf.get(s, absent) for s in map(stem, terms)}
        total = sum(weights.values())
        if not total:
            return 0.0
        best = max(
            (sum(weights[s] for s in weights.keys() & ch["stems"]) for ch in self._chunks),
            default=0.0,
        )
        return best / total

    def rank_articles(
        self,
        terms: List[str],
        folder: Optional[str] = None,
        source: Optional[str] = None,
    ) -> List[Tuple[float, Dict]]:
        """Pontua cada ARTIGO inteiro (soma dos seus trechos) por BM25.

        O idf é recalculado no nível do artigo: um termo presente em quase
        todos os artigos pesa pouco, mesmo que apareça em muitos trechos.
        Devolve (score, artigo) com `artigo["chunks"]` para achar o melhor trecho.
        """
        if not terms:
            return []
        self.refresh()

        stats = self._article_stats(folder, source)
        scored = []
        for a in stats["articles"]:
            s = bm25(a["tf"], a["len"], terms, stats["idf"], stats["avgdl"])
            if s > 0:
                scored.append((s, a))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored

    def _article_stats(self, folder: Optional[str], source: Optional[str]) -> Dict:
        """Totais por artigo de um escopo. Só mudam quando o acervo muda, e
        somá-los a cada pergunta pesa quando muita gente pergunta junto."""
        cached = self._articles.get((folder, source))
        if cached:
            return cached

        arts: Dict[tuple, Dict] = {}
        for ch in self._scoped(folder, source):
            meta = ch["meta"]
            key = (meta.get("folder"), meta.get("source"))
            a = arts.setdefault(key, {"tf": Counter(), "len": 0, "chunks": []})
            a["tf"] += ch["tf"]
            a["len"] += ch["len"]
            a["chunks"].append(ch)

        n = len(arts) or 1
        df: Counter = Counter()
        for a in arts.values():
            df.update(a["tf"].keys())
        stats = {
            "articles": list(arts.values()),
            "idf": _idf(df, n),
            "avgdl": sum(a["len"] for a in arts.values()) / n,
        }
        self._articles[(folder, source)] = stats
        return stats
