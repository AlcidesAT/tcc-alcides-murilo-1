import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

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
