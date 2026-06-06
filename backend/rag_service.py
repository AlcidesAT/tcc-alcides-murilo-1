"""
Pipeline Retrieval-Augmented Generation.

Implementa os dois módulos descritos na proposta do TCC: o módulo de
recuperação (Chroma + embeddings via Ollama) e o módulo de geração
(LLM local via Ollama, orquestrado pelo LangChain).
"""

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
    def _scope_label(folder: Optional[str], source: Optional[str]) -> str:
        if folder and source:
            return f"{folder} / {source}"
        if folder:
            return folder
        return "todas"

    def retrieve(
        self,
        question: str,
        folder: Optional[str] = None,
        source: Optional[str] = None,
    ) -> List[Document]:
        """Recupera os trechos mais relevantes, opcionalmente restringindo a
        busca a uma pasta e/ou a um artigo específico dentro dessa pasta.

        Usa MMR (Maximal Marginal Relevance) para combinar relevância com
        diversidade — evita devolver vários trechos quase idênticos e cobre
        mais partes do(s) artigo(s), o que torna as respostas mais completas.
        """
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
            "sources": self._build_sources(retrieved_docs),
            "scope": self._scope_label(folder, source),
        }

    def stream_answer(self, question: str, docs: List[Document]):
        """Gera a resposta token a token (para streaming ao front-end)."""
        context = self._format_context(docs)
        chain = self.prompt | self.llm | StrOutputParser()
        for piece in chain.stream({"context": context, "question": question}):
            if piece:
                yield piece
