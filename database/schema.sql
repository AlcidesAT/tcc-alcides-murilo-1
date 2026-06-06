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
-- CREATE DATABASE artigos_db
--     WITH ENCODING = 'UTF8'
--          LC_COLLATE = 'pt_BR.UTF-8'
--          LC_CTYPE   = 'pt_BR.UTF-8'
--          TEMPLATE   = template0;

-- 2) Conecte-se ao banco antes de criar as tabelas:
--    \c artigos_db
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
-- Tabela: questions
-- Histórico de cada pergunta feita ao sistema, com a resposta gerada e o
-- escopo da busca. Os artigos usados ficam em `question_sources`.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS questions (
    id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    question    TEXT         NOT NULL,
    answer      TEXT         NOT NULL,
    scope       VARCHAR(255),                       -- pasta, "pasta / artigo" ou "todas"
    folder      VARCHAR(100),                       -- filtro de assunto, se houver
    created_at  TIMESTAMP    NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_questions_created_at ON questions (created_at DESC);

-- ---------------------------------------------------------------------------
-- Tabela: question_sources
-- Artigos utilizados para responder a cada pergunta (um por artigo distinto),
-- com os locais citados (ex.: "linha 33, linha 149") e um trecho representativo.
-- Apaga em cascata se a pergunta for removida.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS question_sources (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    question_id  UUID         NOT NULL REFERENCES questions (id) ON DELETE CASCADE,
    folder       VARCHAR(100) NOT NULL,
    article      VARCHAR(255) NOT NULL,
    locations    VARCHAR(255),
    snippet      TEXT
);

CREATE INDEX IF NOT EXISTS idx_question_sources_question ON question_sources (question_id);

-- ===========================================================================
-- NOTA — Autenticação de usuários
-- A camada de login/cadastro (tabela `users` e vínculo `articles.user_id`)
-- será adicionada na SEGUNDA ENTREGA do TCC. Quando isso ocorrer, recrie a
-- tabela `users` e adicione a coluna/foreign key correspondente em `articles`.
-- ===========================================================================
