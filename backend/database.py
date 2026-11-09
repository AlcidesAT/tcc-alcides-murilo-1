import json
import re

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import DATABASE_URL, SURVEY_FILE

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


# Visões só de leitura, para abrir a coleta num cliente de banco (DBeaver,
# psql) sem decifrar JSON: os dados continuam nas tabelas acima.
_VIEW_PERGUNTAS = """
CREATE VIEW vw_perguntas_turma AS
SELECT i.created_at                           AS data_utc,
       left(i.session_id::text, 8)            AS sessao,
       i.question                             AS pergunta,
       i.standalone_question                  AS pergunta_buscada,
       i.answer                               AS resposta,
       length(i.answer)                       AS caracteres,
       round(i.response_ms / 1000.0, 1)       AS tempo_s,
       round(i.groundedness::numeric, 3)      AS fundamentacao,
       round(i.question_coverage::numeric, 3) AS cobertura_pergunta,
       i.level                                AS nivel,
       e.rating                               AS nota,
       e.comment                              AS comentario_nota,
       CASE WHEN jsonb_typeof(i.sources) = 'array' THEN
            (SELECT string_agg(s ->> 'source', ' | ') FROM jsonb_array_elements(i.sources) s)
       END                                    AS artigos,
       i.scope                                AS escopo,
       i.memory_mode                          AS memoria,
       i.llm_model                            AS modelo,
       i.session_id                           AS sessao_id,
       i.id                                   AS pergunta_id
  FROM interactions i
  LEFT JOIN answer_evaluations e ON e.interaction_id = i.id
"""

_SAFE_ID = re.compile(r"^[a-z_][a-z0-9_]{0,50}$")
_SURVEY_FIXED = {"enviado_utc", "atualizado_utc", "sessao", "versao", "comentario", "sessao_id"}


def _survey_view_sql() -> tuple:
    """Uma coluna por afirmação de questionario.json (lido na inicialização)."""
    with open(SURVEY_FILE, encoding="utf-8") as f:
        statements = json.load(f)["afirmacoes"]
    ids = [s["id"] for s in statements]
    bad = [i for i in ids if not _SAFE_ID.match(i) or i in _SURVEY_FIXED]
    if bad:
        raise ValueError(f"id de afirmação inválido para coluna: {bad}")
    columns = "".join(f",\n       (r.answers ->> '{i}')::smallint AS {i}" for i in ids)
    create = f"""
CREATE VIEW vw_questionario AS
SELECT r.created_at                AS enviado_utc,
       r.updated_at                AS atualizado_utc,
       left(r.session_id::text, 8) AS sessao,
       r.survey_version            AS versao{columns},
       r.comment                   AS comentario,
       r.session_id                AS sessao_id
  FROM survey_responses r
"""
    # Aspas dobradas para o SQL e ":" escapado para o text() do SQLAlchemy.
    literal = lambda s: "'" + s.replace("'", "''").replace(":", "\\:") + "'"
    comments = [
        f"COMMENT ON COLUMN vw_questionario.{s['id']} IS "
        + literal(f"{s.get('criterio', '')}: {s.get('texto', '')} (1 a 5)")
        for s in statements
    ]
    return create, comments


def _create_views(conn) -> None:
    conn.execute(text("DROP VIEW IF EXISTS vw_perguntas_turma"))
    conn.execute(text(_VIEW_PERGUNTAS))
    conn.execute(text(
        "COMMENT ON VIEW vw_perguntas_turma IS "
        "'Perguntas feitas com o login da turma, com a resposta e a nota dada (leitura)'"
    ))
    try:
        create, comments = _survey_view_sql()
    except Exception as exc:
        print(f"[WARNING] Visão vw_questionario não criada: {exc}")
        return
    conn.execute(text("DROP VIEW IF EXISTS vw_questionario"))
    conn.execute(text(create))
    conn.execute(text(
        "COMMENT ON VIEW vw_questionario IS "
        "'Questionário de avaliação, uma linha por participante e uma coluna por afirmação (leitura)'"
    ))
    for sql in comments:
        conn.execute(text(sql))


def init_db():
    import models  # noqa: F401 — registra modelos no Base.metadata
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        for sql in _MIGRATIONS:
            conn.execute(text(sql))
    # À parte: uma visão com problema não pode desligar a coleta.
    try:
        with engine.begin() as conn:
            _create_views(conn)
    except Exception as exc:
        print(f"[WARNING] Visões de leitura não criadas: {exc}")
