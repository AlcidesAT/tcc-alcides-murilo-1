"""
Pipeline Retrieval-Augmented Generation.

Implementa os dois módulos descritos na proposta do TCC — recuperação (Chroma +
embeddings via Ollama + BM25) e geração (LLM local via Ollama, orquestrado pelo
LangChain) — e os acréscimos da segunda entrega: memória de pergunta e
avaliação automática da precisão das respostas.

Fluxo de uma pergunta:

    prepare()  -> memória (resolve perguntas de acompanhamento) + busca híbrida + referências
    stream_answer() / generate()  -> resposta do LLM com histórico e trechos
    evaluate() -> fundamentação da resposta nos trechos recuperados
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama, OllamaEmbeddings

from config import (
    COLLECTION_NAME,
    DEFAULT_FOLDER,
    EMBEDDING_MODEL,
    LLM_MODEL,
    LLM_TEMPERATURE,
    MEMORY_MAX_TURNS,
    OLLAMA_BASE_URL,
    VECTORSTORE_DIR,
)
from document_processor import load_and_split
from rag.evaluation import evaluate_answer
from rag.lexical import LexicalIndex
from rag.catalog import answer_catalog, is_catalog_question
from rag.memory import (
    QuestionCondenser,
    Resolution,
    Turn,
    format_history,
    normalize_history,
)
from rag.prompts import ANSWER_PROMPT, HISTORY_BLOCK
from rag.retrieval import HybridRetriever, location_label, scope_label


@dataclass
class RAGContext:
    """Tudo o que foi decidido antes da geração de uma resposta."""

    question: str
    resolution: Resolution
    folder: Optional[str]
    source: Optional[str]
    history: List[Turn] = field(default_factory=list)
    docs: List[Document] = field(default_factory=list)
    sources: List[Dict] = field(default_factory=list)
    # Pergunta sobre o acervo: resposta montada direto do índice, sem o LLM.
    catalog_answer: Optional[str] = None

    @property
    def standalone_question(self) -> str:
        return self.resolution.standalone

    @property
    def scope(self) -> str:
        return scope_label(self.folder, self.source)

    @property
    def used_memory(self) -> bool:
        """A memória mudou a interpretação da pergunta (acompanhamento)?"""
        return self.resolution.follow_up

    def meta(self) -> Dict:
        """Informações da memória enviadas à interface."""
        return {
            "standalone_question": self.standalone_question,
            "used_memory": self.used_memory,
            "memory_mode": self.resolution.mode,
            "memory_turns": len(self.history),
            "memory_max_turns": MEMORY_MAX_TURNS,
        }


class RAGService:
    """Encapsula o ciclo de vida do índice vetorial e a cadeia RAG."""

    def __init__(self) -> None:
        self.model_name = LLM_MODEL
        self.embeddings = OllamaEmbeddings(
            model=EMBEDDING_MODEL,
            base_url=OLLAMA_BASE_URL,
        )
        self.llm = ChatOllama(
            model=LLM_MODEL,
            base_url=OLLAMA_BASE_URL,
            temperature=LLM_TEMPERATURE,
        )
        self.vectorstore = Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=self.embeddings,
            persist_directory=str(VECTORSTORE_DIR),
        )
        self.lexical = LexicalIndex(self.vectorstore)
        self.retriever = HybridRetriever(self.vectorstore, self.lexical)
        # Reescrita determinística (temperatura 0): a mesma conversa produz
        # sempre a mesma pergunta de busca.
        self.condenser = QuestionCondenser(
            ChatOllama(model=LLM_MODEL, base_url=OLLAMA_BASE_URL, temperature=0)
        )
        self.answer_chain = (
            ChatPromptTemplate.from_template(ANSWER_PROMPT) | self.llm | StrOutputParser()
        )

    # ------------------------------------------------------------------
    # Acervo (indexação, listagem e remoção)
    # ------------------------------------------------------------------

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
        return [
            {
                "folder": entry["folder"],
                "chunks": entry["chunks"],
                "documents": len(entry["sources"]),
            }
            for _, entry in sorted(folders.items())
        ]

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

    # ------------------------------------------------------------------
    # Pergunta -> resposta
    # ------------------------------------------------------------------

    def prepare(
        self,
        question: str,
        folder: Optional[str] = None,
        source: Optional[str] = None,
        history: Optional[Iterable] = None,
    ) -> RAGContext:
        """Aplica a memória da conversa e recupera trechos e referências.

        Separado da geração para que falhas (ex.: Ollama indisponível) virem
        um status HTTP adequado antes de o streaming começar.
        """
        turns = normalize_history(history)
        resolution = self.condenser.resolve(question, turns)

        if not source and is_catalog_question(question):
            answer, sources = answer_catalog(
                resolution.standalone, self.list_documents(folder), self.lexical, folder
            )
            return RAGContext(
                question=question,
                resolution=resolution,
                folder=folder,
                source=source,
                history=turns,
                sources=sources,
                catalog_answer=answer,
            )

        docs = self.retriever.retrieve(resolution.queries, folder, source)
        sources = self.retriever.build_references(
            " ".join(resolution.queries), docs, folder, source
        )
        return RAGContext(
            question=question,
            resolution=resolution,
            folder=folder,
            source=source,
            history=turns,
            docs=docs,
            sources=sources,
        )

    def _format_context(self, docs: List[Document]) -> str:
        blocks = []
        for i, doc in enumerate(docs, start=1):
            src = doc.metadata.get("source", "?")
            folder = doc.metadata.get("folder", "?")
            loc = location_label(doc.metadata)
            blocks.append(
                f"[Trecho {i} | pasta: {folder} | fonte: {src} | {loc}]\n{doc.page_content}"
            )
        return "\n\n".join(blocks) if blocks else "(nenhum trecho recuperado)"

    def _prompt_inputs(self, ctx: RAGContext) -> Dict:
        # O modelo responde à pergunta ORIGINAL do usuário. Em perguntas de
        # acompanhamento, o histórico diz a que ela se refere; a reescrita
        # serve só para a busca — reescritas de modelos pequenos às vezes
        # desviam o sentido ("quais limitações" -> "quem identificou…").
        extra = ""
        if ctx.used_memory:
            extra = HISTORY_BLOCK.format(history=format_history(ctx.history))
        return {
            "extra": extra,
            "context": self._format_context(ctx.docs),
            "question": ctx.question,
        }

    def stream_answer(self, ctx: RAGContext) -> Iterator[str]:
        """Gera a resposta token a token (para streaming ao front-end)."""
        if ctx.catalog_answer is not None:
            yield ctx.catalog_answer
            return
        for piece in self.answer_chain.stream(self._prompt_inputs(ctx)):
            if piece:
                yield piece

    def generate(self, ctx: RAGContext) -> str:
        """Gera a resposta de uma vez."""
        if ctx.catalog_answer is not None:
            return ctx.catalog_answer
        return self.answer_chain.invoke(self._prompt_inputs(ctx))

    def evaluate(self, ctx: RAGContext, answer: str) -> Dict:
        """Métricas automáticas de precisão da resposta (ver rag/evaluation.py)."""
        if ctx.catalog_answer is not None:
            # Lista tirada do próprio índice: não há o que medir contra trechos.
            return {
                "groundedness": None,
                "question_coverage": None,
                "sentences": 0,
                "supported_sentences": 0,
                "level": "acervo",
            }
        return evaluate_answer(ctx.standalone_question, answer, ctx.docs)

    def result(self, ctx: RAGContext, answer: str) -> Dict:
        """Resposta final com fontes, escopo, métricas e dados da memória."""
        return {
            "answer": answer,
            "sources": ctx.sources,
            "scope": ctx.scope,
            "evaluation": self.evaluate(ctx, answer),
            "model": self.model_name,
            **ctx.meta(),
        }

    def ask(
        self,
        question: str,
        folder: Optional[str] = None,
        source: Optional[str] = None,
        history: Optional[Iterable] = None,
    ) -> Dict:
        """Executa o pipeline RAG completo (resposta de uma vez)."""
        ctx = self.prepare(question, folder, source, history)
        return self.result(ctx, self.generate(ctx))
