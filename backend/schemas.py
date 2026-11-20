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
    passages: list = Field(default_factory=list)
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


class LoginRequest(BaseModel):
    username: str = Field(max_length=50)
    password: str = Field(max_length=200)
