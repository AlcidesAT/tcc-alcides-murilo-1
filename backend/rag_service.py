"""
Pipeline Retrieval-Augmented Generation.

Implementa os dois módulos descritos na proposta do TCC: o módulo de
recuperação (Chroma + embeddings via Ollama) e o módulo de geração
(LLM local via Ollama, orquestrado pelo LangChain).
"""

import math
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_ollama import ChatOllama, OllamaEmbeddings

from config import (
    COLLECTION_NAME,
    DEFAULT_FOLDER,
    EMBEDDING_MODEL,
    LLM_MODEL,
    MMR_FETCH_K,
    MMR_LAMBDA,
    OLLAMA_BASE_URL,
    REFERENCES_MAX,
    REFERENCES_MIN_RATIO,
    RETRIEVAL_K,
    VECTORSTORE_DIR,
)
from document_processor import load_and_split


PROMPT_TEMPLATE = """Você é um assistente especializado em responder perguntas sobre artigos científicos.
Baseie-se nos trechos fornecidos abaixo para responder à pergunta do usuário.
Você pode sintetizar, relacionar e interpretar as informações dos trechos para
elaborar uma resposta completa e bem estruturada — sem inventar dados que não
estejam apoiados no contexto. Se os trechos trouxerem apenas informação parcial,
responda com o que for possível e indique o que ficou em aberto. Só diga que não
há informação suficiente quando os trechos realmente não tiverem nenhuma relação
com a pergunta.
Responda em português do Brasil, de forma clara, objetiva e fundamentada,
citando, quando útil, os trechos/artigos que embasam a resposta.

Contexto recuperado dos artigos:
{context}

Pergunta: {question}

Resposta:"""


# Palavras muito comuns em português, ignoradas na busca por palavra-chave para
# não diluir o sinal dos termos realmente informativos (ex.: "SUS", "biópsia").
_STOPWORDS = {
    "a", "o", "as", "os", "um", "uma", "uns", "umas", "de", "do", "da", "dos",
    "das", "no", "na", "nos", "nas", "em", "por", "para", "com", "sem", "sob",
    "e", "ou", "que", "qual", "quais", "quando", "como", "onde", "porque",
    "se", "ao", "aos", "à", "às", "the", "is", "of", "sobre", "entre", "ser",
    "sua", "seu", "suas", "seus", "isso", "este", "esta", "esse", "essa",
    "qual", "me", "minha", "meu", "ele", "ela", "foi", "são", "tem", "há",
}


def _tokenize(text: str) -> List[str]:
    """Normaliza para minúsculas, remove acentos e separa em termos úteis."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    tokens = re.findall(r"[a-z0-9]+", text)
    return [t for t in tokens if len(t) >= 2 and t not in _STOPWORDS]


class RAGService:
    """Encapsula o ciclo de vida do índice vetorial e a cadeia RAG."""

    def __init__(self) -> None:
        self.embeddings = OllamaEmbeddings(
            model=EMBEDDING_MODEL,
            base_url=OLLAMA_BASE_URL,
        )
        self.llm = ChatOllama(
            model=LLM_MODEL,
            base_url=OLLAMA_BASE_URL,
            temperature=0.2,
        )
        self.vectorstore = Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=self.embeddings,
            persist_directory=str(VECTORSTORE_DIR),
        )
        self.prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)

        # Índice léxico (BM25) construído sob demanda para a busca por
        # palavra-chave. `_lex_count` guarda o nº de chunks usado na última
        # construção, para reconstruir quando o acervo muda (upload/remoção).
        self._lex: Optional[Dict] = None
        self._lex_count: int = -1

    def index_document(
        self, file_path: Path, source_name: str, folder: str
    ) -> int:
        """Adiciona um artigo a uma pasta. Retorna a quantidade de chunks."""
        chunks = load_and_split(file_path, source_name, folder)
        if not chunks:
            return 0
        ids = [f"{folder}::{source_name}::chunk-{i}" for i in range(len(chunks))]
        self.vectorstore.add_documents(documents=chunks, ids=ids)
        return len(chunks)

    def _all_metadatas(self) -> List[dict]:
        raw = self.vectorstore.get(include=["metadatas"])
        return [m or {} for m in (raw.get("metadatas") or [])]

    def list_folders(self) -> List[Dict]:
        """Lista pastas com contagem de chunks e de artigos distintos."""
        folders: Dict[str, Dict] = {}
        for md in self._all_metadatas():
            folder = md.get("folder") or DEFAULT_FOLDER
            source = md.get("source", "desconhecido")
            entry = folders.setdefault(
                folder, {"folder": folder, "chunks": 0, "sources": set()}
            )
            entry["chunks"] += 1
            entry["sources"].add(source)
        result = []
        for f in sorted(folders.keys()):
            entry = folders[f]
            result.append(
                {
                    "folder": entry["folder"],
                    "chunks": entry["chunks"],
                    "documents": len(entry["sources"]),
                }
            )
        return result

    def list_documents(self, folder: Optional[str] = None) -> List[Dict]:
        """Lista artigos indexados, opcionalmente filtrando por pasta."""
        counts: Dict[tuple, int] = {}
        for md in self._all_metadatas():
            f = md.get("folder") or DEFAULT_FOLDER
            if folder is not None and f != folder:
                continue
            src = md.get("source", "desconhecido")
            counts[(f, src)] = counts.get((f, src), 0) + 1
        return [
            {"folder": f, "source": s, "chunks": c}
            for (f, s), c in sorted(counts.items())
        ]

    def delete_document(self, folder: str, source_name: str) -> int:
        """Remove todos os chunks de um artigo específico dentro de uma pasta."""
        raw = self.vectorstore.get(
            where={"$and": [{"folder": folder}, {"source": source_name}]},
            include=["metadatas"],
        )
        ids = raw.get("ids", []) or []
        if ids:
            self.vectorstore.delete(ids=ids)
        return len(ids)

    def delete_folder(self, folder: str) -> int:
        """Remove todos os chunks de uma pasta inteira."""
        raw = self.vectorstore.get(where={"folder": folder}, include=["metadatas"])
        ids = raw.get("ids", []) or []
        if ids:
            self.vectorstore.delete(ids=ids)
        return len(ids)

    @staticmethod
    def _location_label(md: dict) -> str:
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

    def _format_context(self, docs: List[Document]) -> str:
        blocks = []
        for i, doc in enumerate(docs, start=1):
            src = doc.metadata.get("source", "?")
            folder = doc.metadata.get("folder", "?")
            loc = self._location_label(doc.metadata)
            blocks.append(
                f"[Trecho {i} | pasta: {folder} | fonte: {src} | {loc}]\n{doc.page_content}"
            )
        return "\n\n".join(blocks) if blocks else "(nenhum trecho recuperado)"

    def _build_sources(self, docs: List[Document]) -> List[Dict]:
        return [
            {
                "folder": d.metadata.get("folder", "?"),
                "source": d.metadata.get("source", "?"),
                "location": self._location_label(d.metadata),
                "snippet": d.page_content[:240].strip().replace("\n", " ") + "…",
            }
            for d in docs
        ]

    @staticmethod
    def _ref_entry(text: str, meta: dict) -> Dict:
        source = meta.get("source", "?")
        return {
            "folder": meta.get("folder", "?"),
            "source": source,
            "location": RAGService._location_label(meta),
            "snippet": text[:240].strip().replace("\n", " ") + "…",
            "file_type": Path(source).suffix.lower(),
        }

    def _chunk_bm25(self, tf: Counter, length: int, terms: List[str]) -> float:
        """Score BM25 de um único chunk (usa idf/avgdl do índice por chunk)."""
        lex = self._lex
        idf, avgdl = lex["idf"], (lex["avgdl"] or 1.0)
        k1, b = 1.5, 0.75
        score = 0.0
        for t in terms:
            f = tf.get(t, 0)
            if not f:
                continue
            denom = f + k1 * (1 - b + b * length / avgdl)
            score += idf.get(t, 0.0) * (f * (k1 + 1)) / denom
        return score

    def build_references(
        self,
        question: str,
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
        terms = _tokenize(question)
        self._ensure_lexical_index()
        lex = self._lex

        if terms and lex and lex["chunks"]:
            # Agrega os chunks por artigo (respeitando o filtro de escopo).
            arts: Dict[tuple, Dict] = {}
            for ch in lex["chunks"]:
                meta = ch["meta"]
                if folder and meta.get("folder") != folder:
                    continue
                if source and meta.get("source") != source:
                    continue
                key = (meta.get("folder"), meta.get("source"))
                a = arts.setdefault(key, {"tf": Counter(), "len": 0, "chunks": []})
                a["tf"] += ch["tf"]
                a["len"] += ch["len"]
                a["chunks"].append(ch)

            if arts:
                n = len(arts)
                avgdl = sum(a["len"] for a in arts.values()) / n
                df: Counter = Counter()
                for a in arts.values():
                    for t in a["tf"]:
                        df[t] += 1
                k1, b = 1.5, 0.75

                scored = []
                for key, a in arts.items():
                    s = 0.0
                    for t in terms:
                        f = a["tf"].get(t, 0)
                        if not f:
                            continue
                        idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                        denom = f + k1 * (1 - b + b * a["len"] / avgdl)
                        s += idf * (f * (k1 + 1)) / denom
                    if s > 0:
                        scored.append((s, a))

                if scored:
                    scored.sort(key=lambda x: x[0], reverse=True)
                    cutoff = scored[0][0] * REFERENCES_MIN_RATIO
                    refs = []
                    for s, a in scored:
                        if s < cutoff or len(refs) >= REFERENCES_MAX:
                            break
                        # Melhor trecho do artigo para o snippet/localização.
                        best = max(
                            a["chunks"],
                            key=lambda ch: self._chunk_bm25(ch["tf"], ch["len"], terms),
                        )
                        refs.append(self._ref_entry(best["text"], best["meta"]))
                    return refs

        # Fallback: artigos distintos da busca semântica, na ordem recuperada.
        refs, seen = [], set()
        for d in context_docs:
            key = (d.metadata.get("folder"), d.metadata.get("source"))
            if key in seen:
                continue
            seen.add(key)
            refs.append(self._ref_entry(d.page_content, d.metadata))
            if len(refs) >= REFERENCES_MAX:
                break
        return refs

    @staticmethod
    def _scope_label(folder: Optional[str], source: Optional[str]) -> str:
        if folder and source:
            return f"{folder} / {source}"
        if folder:
            return folder
        return "todas"

    @staticmethod
    def _doc_key(meta: dict) -> tuple:
        """Identificador estável de um chunk (para deduplicar na fusão)."""
        return (
            meta.get("folder"),
            meta.get("source"),
            meta.get("chunk_index"),
            meta.get("loc_value"),
        )

    def _ensure_lexical_index(self) -> None:
        """Constrói (ou reconstrói) o índice BM25 a partir de todos os chunks.

        Só refaz o trabalho quando a quantidade de chunks muda, mantendo o
        custo desprezível entre perguntas.
        """
        count = self.vectorstore._collection.count()
        if self._lex is not None and self._lex_count == count:
            return

        raw = self.vectorstore.get(include=["documents", "metadatas"])
        docs = raw.get("documents") or []
        metas = raw.get("metadatas") or []

        chunks = []
        df: Counter = Counter()
        total_len = 0
        for text, meta in zip(docs, metas):
            tokens = _tokenize(text)
            tf = Counter(tokens)
            chunks.append(
                {"text": text, "meta": meta or {}, "tf": tf, "len": len(tokens)}
            )
            total_len += len(tokens)
            for term in tf:
                df[term] += 1

        n = len(chunks) or 1
        idf = {
            term: math.log(1 + (n - freq + 0.5) / (freq + 0.5))
            for term, freq in df.items()
        }
        self._lex = {
            "chunks": chunks,
            "idf": idf,
            "avgdl": (total_len / n) if n else 0.0,
        }
        self._lex_count = count

    def _keyword_search(
        self,
        question: str,
        folder: Optional[str],
        source: Optional[str],
        k: int,
    ) -> List[Document]:
        """Busca por palavra-chave (BM25) sobre todos os chunks indexados.

        Garante que termos literais da pergunta (ex.: a sigla "SUS") recuperem
        os trechos onde aparecem, mesmo quando a busca semântica não os destaca.
        """
        query_terms = _tokenize(question)
        if not query_terms:
            return []

        self._ensure_lexical_index()
        lex = self._lex
        if not lex or not lex["chunks"]:
            return []

        idf = lex["idf"]
        avgdl = lex["avgdl"] or 1.0
        k1, b = 1.5, 0.75

        scored = []
        for ch in lex["chunks"]:
            meta = ch["meta"]
            if folder and meta.get("folder") != folder:
                continue
            if source and meta.get("source") != source:
                continue

            tf = ch["tf"]
            score = 0.0
            for term in query_terms:
                f = tf.get(term, 0)
                if not f:
                    continue
                denom = f + k1 * (1 - b + b * ch["len"] / avgdl)
                score += idf.get(term, 0.0) * (f * (k1 + 1)) / denom
            if score > 0:
                scored.append((score, ch))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            Document(page_content=ch["text"], metadata=ch["meta"])
            for _, ch in scored[:k]
        ]

    def _vector_search(
        self,
        question: str,
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
        return retriever.invoke(question)

    def _fuse(self, ranked_lists: List[List[Document]], k: int = 60) -> List[Document]:
        """Reciprocal Rank Fusion: combina várias listas ordenadas em uma só.

        Cada documento soma 1/(k + posição) de cada lista em que aparece; assim,
        trechos bem ranqueados na busca semântica E na lexical sobem ao topo.
        """
        scores: Dict[tuple, float] = {}
        docs: Dict[tuple, Document] = {}
        for ranked in ranked_lists:
            for rank, doc in enumerate(ranked):
                key = self._doc_key(doc.metadata)
                scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
                docs.setdefault(key, doc)
        ordered = sorted(scores.keys(), key=lambda key: scores[key], reverse=True)
        return [docs[key] for key in ordered]

    def retrieve(
        self,
        question: str,
        folder: Optional[str] = None,
        source: Optional[str] = None,
    ) -> List[Document]:
        """Recupera os trechos mais relevantes via **busca híbrida**.

        Combina a busca semântica (MMR sobre os embeddings) com a busca por
        palavra-chave (BM25), fundindo as duas por Reciprocal Rank Fusion. Isso
        cobre tanto perguntas conceituais quanto termos/siglas literais (ex.:
        "SUS"), percorrendo todos os artigos. Restringível a pasta/artigo.
        """
        vector_docs = self._vector_search(question, folder, source)
        keyword_docs = self._keyword_search(question, folder, source, k=RETRIEVAL_K)

        if not keyword_docs:
            return vector_docs[:RETRIEVAL_K]

        fused = self._fuse([vector_docs, keyword_docs])
        return fused[:RETRIEVAL_K]

    def ask(
        self,
        question: str,
        folder: Optional[str] = None,
        source: Optional[str] = None,
    ) -> Dict:
        """Executa o pipeline RAG completo (resposta de uma vez)."""
        retrieved_docs = self.retrieve(question, folder, source)

        chain = (
            {
                "context": lambda x: self._format_context(retrieved_docs),
                "question": RunnablePassthrough(),
            }
            | self.prompt
            | self.llm
            | StrOutputParser()
        )
        answer = chain.invoke(question)

        return {
            "answer": answer,
            "sources": self.build_references(question, retrieved_docs, folder, source),
            "scope": self._scope_label(folder, source),
        }

    def stream_answer(self, question: str, docs: List[Document]):
        """Gera a resposta token a token (para streaming ao front-end)."""
        context = self._format_context(docs)
        chain = self.prompt | self.llm | StrOutputParser()
        for piece in chain.stream({"context": context, "question": question}):
            if piece:
                yield piece
