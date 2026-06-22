"""
Inspeção da base vetorial (ChromaDB) — útil para visualizar/printar o conteúdo
indexado do sistema RAG (coleção, total de vetores, dimensão dos embeddings e
exemplos de chunks com seus metadados).

Não altera nada: apenas lê a base persistida em `data/vectorstore/`.

Uso (a partir da pasta `backend`):
    python inspect_chroma.py
"""

import chromadb

from config import COLLECTION_NAME, EMBEDDING_MODEL, VECTORSTORE_DIR


def main() -> None:
    client = chromadb.PersistentClient(path=str(VECTORSTORE_DIR))
    col = client.get_collection(COLLECTION_NAME)

    print("=" * 60)
    print("  ChromaDB — Base Vetorial do Sistema RAG")
    print("=" * 60)
    print(f"Local da base   : {VECTORSTORE_DIR}")
    print(f"Coleção         : {col.name}")
    print(f"Total de chunks : {col.count()} vetores indexados")

    data = col.get(limit=3, include=["metadatas", "documents", "embeddings"])
    embeddings = data.get("embeddings")
    dim = len(embeddings[0]) if embeddings is not None and len(embeddings) else "?"
    print(f"Dimensão        : {dim} (embeddings '{EMBEDDING_MODEL}')")

    # Artigos distintos por assunto.
    todos = col.get(include=["metadatas"])
    por_assunto: dict[str, set] = {}
    for meta in todos["metadatas"]:
        por_assunto.setdefault(meta.get("folder", "?"), set()).add(meta.get("source"))
    print(f"Assuntos        : {len(por_assunto)} | Artigos: "
          f"{sum(len(v) for v in por_assunto.values())}")
    for assunto, artigos in sorted(por_assunto.items()):
        print(f"   - {assunto}: {len(artigos)} artigo(s)")

    print("\n" + "-" * 60)
    print("  Exemplos de chunks armazenados")
    print("-" * 60)
    for i, (meta, doc) in enumerate(zip(data["metadatas"], data["documents"]), 1):
        print(f"[{i}] artigo : {meta.get('source')}")
        print(f"    assunto: {meta.get('folder')} | "
              f"{meta.get('loc_kind')} {meta.get('loc_value')}")
        print(f"    trecho : {doc[:90].strip()}...")
        print()


if __name__ == "__main__":
    main()
