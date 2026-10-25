-- ===========================================================================
-- Esquema do banco de dados — Sistema Inteligente de Consulta a Artigos
-- Científicos (RAG)  ·  TCC Unoesc 2026
--
-- Banco: PostgreSQL
--
-- Este script é OPCIONAL: a aplicação cria as tabelas automaticamente na
-- inicialização (SQLAlchemy `Base.metadata.create_all`). Use-o quando quiser
-- preparar o banco manualmente ou inspecionar/entender a estrutura.
--
-- Uso (no terminal, com o PostgreSQL instalado):
--   psql -U postgres -f database/schema.sql
-- ===========================================================================

-- 1) Cria o banco (rode esta parte conectado ao banco "postgres").
--    Se o banco já existir, ignore o erro de "already exists".
-- ---------------------------------------------------------------------------
-- CREATE DATABASE tcc_rag
--     WITH ENCODING = 'UTF8'
--          LC_COLLATE = 'pt_BR.UTF-8'
--          LC_CTYPE   = 'pt_BR.UTF-8'
--          TEMPLATE   = template0;

-- 2) Conecte-se ao banco antes de criar as tabelas:
--    \c tcc_rag
-- ---------------------------------------------------------------------------

-- Suporte a UUID (gen_random_uuid disponível no módulo pgcrypto).
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------------
-- Tabela: articles
-- Arquiva os metadados de cada artigo enviado e indexado pelo sistema RAG.
-- O conteúdo vetorizado fica no ChromaDB (data/vectorstore); aqui guardamos
-- apenas o registro/auditoria de cada upload.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS articles (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    folder          VARCHAR(100) NOT NULL,
    filename        VARCHAR(255) NOT NULL,
    stored_as       VARCHAR(255) NOT NULL,
    file_size       BIGINT       NOT NULL,
    file_type       VARCHAR(10)  NOT NULL,
    chunks_indexed  INTEGER      NOT NULL DEFAULT 0,
    uploaded_at     TIMESTAMP    NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_articles_folder       ON articles (folder);
CREATE INDEX IF NOT EXISTS idx_articles_uploaded_at  ON articles (uploaded_at DESC);

-- ---------------------------------------------------------------------------
-- Tabela: question_sources
-- Log dos artigos usados para fundamentar cada resposta (um registro por
-- artigo distinto), com os locais citados (ex.: "linha 33, linha 149") e um
-- trecho representativo. Registro independente, sem vínculo com perguntas.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS question_sources (
    id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    folder      VARCHAR(100) NOT NULL,
    article     VARCHAR(255) NOT NULL,
    locations   VARCHAR(255),
    snippet     TEXT,
    created_at  TIMESTAMP    NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_question_sources_created_at ON question_sources (created_at DESC);

-- ---------------------------------------------------------------------------
-- Tabela: participant_sessions
-- Cada entrada com o login da turma (participante dos testes). Todos usam o
-- mesmo login; cada entrada é uma sessão anônima, que agrupa as perguntas,
-- as notas e o questionário de um participante sem guardar nomes.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS participant_sessions (
    id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    token       VARCHAR(64)  NOT NULL UNIQUE,
    username    VARCHAR(50)  NOT NULL,
    started_at  TIMESTAMP    NOT NULL DEFAULT now(),
    ended_at    TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- Tabela: interactions
-- Perguntas feitas com o login da turma e as respostas geradas, com as
-- métricas automáticas, o modelo e o tempo de resposta (coleta da pesquisa).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS interactions (
    id                   UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id           UUID          REFERENCES participant_sessions(id),
    question             TEXT          NOT NULL,
    standalone_question  TEXT,
    answer               TEXT          NOT NULL,
    scope                VARCHAR(255),
    sources              JSONB,
    memory_mode          VARCHAR(20),
    groundedness         DOUBLE PRECISION,
    question_coverage    DOUBLE PRECISION,
    level                VARCHAR(20),
    llm_model            VARCHAR(100),
    response_ms          INTEGER,
    created_at           TIMESTAMP     NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_interactions_session_id ON interactions (session_id);
CREATE INDEX IF NOT EXISTS ix_interactions_created_at ON interactions (created_at DESC);

-- ---------------------------------------------------------------------------
-- Tabela: answer_evaluations
-- Nota de precisão (1 a 5) e comentário que um participante deu a uma
-- resposta. Guarda o par pergunta/resposta, as fontes, as métricas
-- automáticas (fundamentação e cobertura) e o modelo usado, e aponta para a
-- pergunta coletada (interaction_id). Uma nova nota substitui a anterior.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS answer_evaluations (
    id                   UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    question             TEXT          NOT NULL,
    standalone_question  TEXT,
    answer               TEXT          NOT NULL,
    scope                VARCHAR(255),
    sources              JSONB,
    used_memory          BOOLEAN       DEFAULT FALSE,
    rating               SMALLINT      NOT NULL CONSTRAINT ck_answer_evaluations_rating CHECK (rating BETWEEN 1 AND 5),
    comment              TEXT,
    groundedness         DOUBLE PRECISION,
    question_coverage    DOUBLE PRECISION,
    level                VARCHAR(20),
    llm_model            VARCHAR(100),
    session_id           UUID          REFERENCES participant_sessions(id),
    interaction_id       UUID          REFERENCES interactions(id),
    created_at           TIMESTAMP     NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_answer_evaluations_created_at ON answer_evaluations (created_at DESC);
CREATE INDEX IF NOT EXISTS ix_answer_evaluations_session_id ON answer_evaluations (session_id);
CREATE INDEX IF NOT EXISTS ix_answer_evaluations_interaction_id ON answer_evaluations (interaction_id);

-- Bancos criados antes destas colunas existirem (o app aplica isto sozinho):
ALTER TABLE answer_evaluations
    ADD COLUMN IF NOT EXISTS session_id UUID REFERENCES participant_sessions(id),
    ADD COLUMN IF NOT EXISTS interaction_id UUID REFERENCES interactions(id);

-- ---------------------------------------------------------------------------
-- Tabela: survey_responses
-- Questionário de avaliação do sistema: uma resposta por sessão de
-- participante. `answers` = {id da afirmação: nota 1 a 5}; as afirmações
-- ficam em data/evaluation/questionario.json.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS survey_responses (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID         NOT NULL UNIQUE REFERENCES participant_sessions(id),
    survey_version  VARCHAR(20),
    answers         JSONB        NOT NULL,
    comment         TEXT,
    created_at      TIMESTAMP    NOT NULL DEFAULT now(),
    updated_at      TIMESTAMP    NOT NULL DEFAULT now()
);

-- ===========================================================================
-- NOTA — Autenticação de usuários
-- Por enquanto há dois logins fixos, definidos no .env: o do Administrador e o
-- login da turma (compartilhado pelos participantes dos testes). Um cadastro
-- de usuários individuais (tabela `users`) pode ser adicionado depois.
-- ===========================================================================
