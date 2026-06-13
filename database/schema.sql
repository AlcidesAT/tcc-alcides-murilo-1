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

-- ===========================================================================
-- NOTA — Autenticação de usuários
-- A camada de login/cadastro (tabela `users` e vínculo `articles.user_id`)
-- será adicionada na SEGUNDA ENTREGA do TCC. Quando isso ocorrer, recrie a
-- tabela `users` e adicione a coluna/foreign key correspondente em `articles`.
-- ===========================================================================
