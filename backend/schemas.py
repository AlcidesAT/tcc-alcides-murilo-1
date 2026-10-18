"""
Esquemas Pydantic (entrada/saída) da API.
"""

from typing import List, Optional

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


class CreateFolderRequest(BaseModel):
    name: str


class AdminLoginRequest(BaseModel):
    password: str


class AutoMetrics(BaseModel):
    groundedness: Optional[float] = None
    question_coverage: Optional[float] = None
    level: Optional[str] = None


class EvaluationRequest(BaseModel):
    """Nota do usuário para uma resposta, com o contexto da resposta avaliada."""

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
