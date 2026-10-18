"""
Pacote do pipeline RAG.

    lexical.py     tokenização e índice BM25 (busca por palavra-chave)
    retrieval.py   busca híbrida (MMR + BM25 + RRF) e seleção de referências
    memory.py      memória de pergunta (histórico e reescrita da pergunta)
    catalog.py     perguntas sobre o acervo (lista de artigos no prompt)
    prompts.py     prompts de geração e de reescrita
    evaluation.py  avaliação automática da precisão das respostas
    service.py     RAGService: fachada usada pela API e pelos scripts
"""

from rag.service import RAGContext, RAGService

__all__ = ["RAGContext", "RAGService"]
