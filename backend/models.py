import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
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


class ParticipantSession(Base):
    """Uma entrada com o login da turma (participante dos testes com usuários).

    Todos usam o mesmo login, mas cada entrada vira uma sessão anônima: dá para
    contar participantes e agrupar perguntas, notas e o questionário sem
    guardar nomes. O token é o que o navegador envia em `X-Auth-Token`; por
    ficar no banco, continua válido se o servidor for reiniciado.
    """

    __tablename__ = "participant_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token = Column(String(64), nullable=False, unique=True, index=True)
    username = Column(String(50), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime)  # preenchido ao clicar em "Sair"


class Interaction(Base):
    """Pergunta feita por um participante e a resposta gerada (coleta da pesquisa).

    Gravada pelo servidor ao fim de cada resposta, com as métricas automáticas,
    o modelo e o tempo de resposta. As notas por estrelas (AnswerEvaluation)
    apontam para cá.
    """

    __tablename__ = "interactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("participant_sessions.id"), index=True)
    question = Column(Text, nullable=False)
    standalone_question = Column(Text)  # como a memória buscou a pergunta
    answer = Column(Text, nullable=False)
    scope = Column(String(255))
    sources = Column(JSONB)  # [{folder, source, location}]
    memory_mode = Column(String(20))  # none / rewrite / expansion
    groundedness = Column(Float)
    question_coverage = Column(Float)
    level = Column(String(20))
    llm_model = Column(String(100))
    response_ms = Column(Integer)  # da pergunta ao fim da resposta
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class SurveyResponse(Base):
    """Questionário de avaliação do sistema (um por sessão de participante).

    `answers` guarda {id_da_afirmação: nota de 1 a 5}; as afirmações ficam em
    data/evaluation/questionario.json, e `survey_version` indica qual versão
    do questionário foi respondida.
    """

    __tablename__ = "survey_responses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True), ForeignKey("participant_sessions.id"), unique=True, nullable=False
    )
    survey_version = Column(String(20))
    answers = Column(JSONB, nullable=False)
    comment = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class AnswerEvaluation(Base):
    """Nota de precisão (1 a 5) que um participante deu a uma resposta.

    Guarda o par pergunta/resposta e as métricas automáticas calculadas no
    momento da resposta, permitindo comparar a nota humana com a fundamentação
    medida e comparar modelos/versões do sistema. `interaction_id` liga a nota
    à pergunta coletada; uma nova nota para a mesma pergunta substitui a anterior.
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
    session_id = Column(UUID(as_uuid=True), ForeignKey("participant_sessions.id"), index=True)
    interaction_id = Column(UUID(as_uuid=True), ForeignKey("interactions.id"), index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
