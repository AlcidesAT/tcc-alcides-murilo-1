"""
Indexa no RAG os artigos que estão dentro das pastas de assunto.

Cada subpasta de `data/documents/` é um "assunto" (grande área). Basta colocar
os arquivos (.pdf / .md / .txt) dentro da pasta do assunto desejado — por
exemplo `data/documents/ciencias-exatas-e-tecnologicas/` — e rodar este script.
Ele indexa, NO PRÓPRIO LUGAR, todos os arquivos que ainda não foram indexados,
e arquiva os metadados na tabela `articles` do PostgreSQL.

Reexecuções são seguras: arquivos já presentes no índice são ignorados.

Pré-requisitos:
  - Ollama em execução (`ollama serve`) com `llama3.2` e `nomic-embed-text`.
  - (Opcional) PostgreSQL acessível para o arquivamento dos metadados.

Uso (a partir da pasta `backend`):
    python seed_articles.py
"""

from config import DOCUMENTS_DIR, SUPPORTED_EXTENSIONS, slugify_folder
from rag_service import RAGService


def main() -> None:
    print("[INFO] Inicializando pipeline RAG (requer o Ollama em execução)...")
    rag = RAGService()

    # Arquivamento no banco é opcional.
    db = None
    Article = None
    try:
        from database import SessionLocal, init_db
        from models import Article as _Article

        init_db()
        db = SessionLocal()
        Article = _Article
        print("[INFO] PostgreSQL conectado — metadados serão arquivados.")
    except Exception as exc:
        print(f"[AVISO] Banco indisponível, seguindo sem arquivar: {exc}")

    total_files = 0
    total_chunks = 0

    area_dirs = sorted(p for p in DOCUMENTS_DIR.iterdir() if p.is_dir())
    for area_dir in area_dirs:
        area = slugify_folder(area_dir.name)

        files = [
            f
            for f in sorted(area_dir.iterdir())
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
        if not files:
            continue

        already_indexed = {d["source"] for d in rag.list_documents(area)}
        pending = [f for f in files if f.name not in already_indexed]

        print(
            f"\n== {area}: {len(files)} arquivo(s) na pasta, "
            f"{len(pending)} a indexar =="
        )
        if not pending:
            print("  (tudo já indexado)")
            continue

        for f in pending:
            try:
                chunks = rag.index_document(f, source_name=f.name, folder=area)
            except Exception as exc:
                print(f"  [ERRO] {f.name}: falha ao indexar — {exc}")
                continue

            total_files += 1
            total_chunks += chunks
            print(f"  [OK] {f.name} -> {chunks} trecho(s)")

            if db is not None and Article is not None:
                try:
                    exists = (
                        db.query(Article)
                        .filter(Article.folder == area, Article.filename == f.name)
                        .first()
                    )
                    if not exists:
                        db.add(
                            Article(
                                folder=area,
                                filename=f.name,
                                stored_as=f.name,
                                file_size=f.stat().st_size,
                                file_type=f.suffix.lower(),
                                chunks_indexed=chunks,
                            )
                        )
                        db.commit()
                except Exception as exc:
                    db.rollback()
                    print(f"       [aviso] não arquivado no banco: {exc}")

    if db is not None:
        db.close()

    if total_files == 0:
        print(
            "\nNenhum arquivo novo para indexar. Coloque os artigos em "
            "'data/documents/<assunto>/' e rode novamente."
        )
    else:
        print(
            f"\nConcluído: {total_files} novo(s) artigo(s) e {total_chunks} "
            "trecho(s) indexado(s). Já pode fazer perguntas na interface."
        )


if __name__ == "__main__":
    main()
