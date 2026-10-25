from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# `create_all` cria tabelas novas, mas não altera as que já existem. Colunas
# acrescentadas depois da criação de uma tabela entram aqui (idempotente).
_MIGRATIONS = [
    """ALTER TABLE answer_evaluations
         ADD COLUMN IF NOT EXISTS session_id UUID REFERENCES participant_sessions(id),
         ADD COLUMN IF NOT EXISTS interaction_id UUID REFERENCES interactions(id)""",
    "CREATE INDEX IF NOT EXISTS ix_answer_evaluations_session_id ON answer_evaluations (session_id)",
    "CREATE INDEX IF NOT EXISTS ix_answer_evaluations_interaction_id ON answer_evaluations (interaction_id)",
]


def init_db():
    import models  # noqa: F401 — registra modelos no Base.metadata
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        for sql in _MIGRATIONS:
            conn.execute(text(sql))
