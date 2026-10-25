"""
Esquemas Pydantic (entrada/saída) da API.
"""

import uuid
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class HistoryTurn(BaseModel):
    """Par pergunta/resposta anterior da conversa (memória de pergunta)."""

    question: str = Field(max_length=4000)
    answer: str = Field(default="", max_length=20000)


class AskRequest(BaseModel):
    question: str
    folder: Optional[str] = None
    source: Optional[str] = None
    history: List[HistoryTurn] = Field(default_factory=list, max_length=50)


class AskResponse(BaseModel):
    answer: str
    sources: list
    scope: str
    evaluation: dict
    model: str
    standalone_question: str
    used_memory: bool
    memory_mode: str
    memory_turns: int
    memory_max_turns: int
    interaction_id: Optional[str] = None  # pergunta registrada (login da turma)
    collected: bool = False


class CreateFolderRequest(BaseModel):
    name: str


class LoginRequest(BaseModel):
    username: str = Field(max_length=50)
    password: str = Field(max_length=200)


class AutoMetrics(BaseModel):
    groundedness: Optional[float] = None
    question_coverage: Optional[float] = None
    level: Optional[str] = None


class EvaluationRequest(BaseModel):
    """Nota do participante para uma resposta, com o contexto da resposta avaliada.

    Com `interaction_id` (pergunta coletada), o servidor usa os dados gravados
    da pergunta; os demais campos ficam como reserva.
    """

    interaction_id: Optional[uuid.UUID] = None
    question: str = Field(min_length=1, max_length=4000)
    standalone_question: Optional[str] = Field(default=None, max_length=4000)
    answer: str = Field(min_length=1, max_length=20000)
    scope: Optional[str] = Field(default=None, max_length=255)
    sources: list = Field(default_factory=list, max_length=20)
    used_memory: bool = False
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = Field(default=None, max_length=2000)
    metrics: AutoMetrics = Field(default_factory=AutoMetrics)
    model: Optional[str] = Field(default=None, max_length=100)


class SurveyRequest(BaseModel):
    """Questionário de avaliação do sistema: {id da afirmação: nota 1 a 5}."""

    answers: Dict[str, int]
    comment: Optional[str] = Field(default=None, max_length=4000)
