import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

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


class Question(Base):
    """Registra cada pergunta feita ao sistema, com a resposta gerada e o
    escopo da busca. Os artigos usados ficam em `question_sources`."""

    __tablename__ = "questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    scope = Column(String(255))  # rótulo do escopo: pasta, "pasta / artigo" ou "todas"
    folder = Column(String(100), nullable=True)  # filtro de assunto, se houver
    created_at = Column(DateTime, default=datetime.utcnow)

    sources = relationship(
        "QuestionSource",
        back_populates="question",
        cascade="all, delete-orphan",
    )


class QuestionSource(Base):
    """Artigo utilizado para responder a uma pergunta (um por artigo distinto)."""

    __tablename__ = "question_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id = Column(
        UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    folder = Column(String(100), nullable=False)
    article = Column(String(255), nullable=False)  # nome do artigo (fonte)
    locations = Column(String(255))  # locais citados, ex.: "linha 33, linha 149"
    snippet = Column(Text)  # trecho representativo

    question = relationship("Question", back_populates="sources")
