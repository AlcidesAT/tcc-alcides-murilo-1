import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    Integer,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from database import Base


class Article(Base):
    """Registro/auditoria de cada artigo enviado e indexado pelo sistema RAG.

    O conteúdo vetorizado fica no ChromaDB; aqui guardamos apenas os metadados
    de cada upload (qual arquivo, em qual assunto, quantos trechos foram
    indexados e quando).

    Observação: o vínculo com usuários (`user_id`) e a tabela `users` serão
    adicionados na segunda entrega do TCC, junto com a camada de login.
    """

    __tablename__ = "articles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    folder = Column(String(100), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    stored_as = Column(String(255), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    file_type = Column(String(10), nullable=False)
    chunks_indexed = Column(Integer, default=0)
    uploaded_at = Column(DateTime, default=datetime.utcnow)


class QuestionSource(Base):
    """Artigo utilizado para responder a uma pergunta (um por artigo distinto).

    Registro independente: não há mais uma tabela `questions` vinculada — cada
    linha é apenas um log de qual artigo foi usado para fundamentar uma resposta.
    """

    __tablename__ = "question_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    folder = Column(String(100), nullable=False)
    article = Column(String(255), nullable=False)  # nome do artigo (fonte)
    locations = Column(String(255))  # locais citados, ex.: "linha 33, linha 149"
    snippet = Column(Text)  # trecho representativo
    created_at = Column(DateTime, default=datetime.utcnow)


class AnswerEvaluation(Base):
    """Avaliação da precisão de uma resposta, feita pelo usuário na interface.

    Só é gravada quando o usuário dá uma nota (1 a 5) — por isso, diferente do
    log de fontes, guarda o par pergunta/resposta: sem ele não há como analisar
    a avaliação. Junto ficam as métricas automáticas calculadas no momento da
    resposta e o modelo usado, permitindo comparar a nota humana com a
    fundamentação medida e comparar modelos/versões do sistema.
    """

    __tablename__ = "answer_evaluations"
    __table_args__ = (CheckConstraint("rating BETWEEN 1 AND 5", name="ck_answer_evaluations_rating"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question = Column(Text, nullable=False)
    standalone_question = Column(Text)  # pergunta reescrita pela memória
    answer = Column(Text, nullable=False)
    scope = Column(String(255))
    sources = Column(JSONB)  # [{folder, source, location}]
    used_memory = Column(Boolean, default=False)
    rating = Column(SmallInteger, nullable=False)  # 1 (imprecisa) a 5 (precisa)
    comment = Column(Text)
    groundedness = Column(Float)  # fundamentação automática (0 a 1)
    question_coverage = Column(Float)  # cobertura da pergunta pelos trechos (0 a 1)
    level = Column(String(20))  # alta / media / baixa / indefinido
    llm_model = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
