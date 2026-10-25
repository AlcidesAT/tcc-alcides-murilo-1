"""
Dependências compartilhadas pelas rotas da API.

  - `get_rag()`: instância única do pipeline RAG (criada na primeira chamada).
  - `get_principal`: quem está fazendo a requisição (leitor, participante ou admin).
  - `require_admin` / `require_participant`: protegem as rotas de cada perfil.

O navegador envia o token recebido no login no cabeçalho `X-Auth-Token`.
"""

import secrets
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from fastapi import Depends, Header, HTTPException

from database import SessionLocal
from models import ParticipantSession
from rag import RAGService

# Token de sessão do administrador, gerado a cada inicialização do servidor.
# Os tokens de participante ficam no banco (participant_sessions).
ADMIN_TOKEN = secrets.token_urlsafe(32)

LEITOR, PARTICIPANTE, ADMIN = "leitor", "participante", "admin"


@dataclass
class Principal:
    role: str
    session_id: Optional[object] = None  # UUID da sessão do participante

    @property
    def is_participant(self) -> bool:
        return self.role == PARTICIPANTE


@lru_cache(maxsize=1)
def get_rag() -> RAGService:
    return RAGService()


def get_principal(x_auth_token: Optional[str] = Header(default=None)) -> Principal:
    """Resolve o perfil pelo token. Sem token (ou token inválido): Leitor."""
    if not x_auth_token:
        return Principal(LEITOR)
    if secrets.compare_digest(x_auth_token, ADMIN_TOKEN):
        return Principal(ADMIN)
    try:
        db = SessionLocal()
        try:
            session = (
                db.query(ParticipantSession)
                .filter(ParticipantSession.token == x_auth_token, ParticipantSession.ended_at.is_(None))
                .first()
            )
        finally:
            db.close()
    except Exception as exc:
        print(f"[WARNING] Não foi possível validar a sessão do participante: {exc}")
        return Principal(LEITOR)
    if session:
        return Principal(PARTICIPANTE, session.id)
    return Principal(LEITOR)


def require_admin(principal: Principal = Depends(get_principal)) -> Principal:
    """Protege as rotas exclusivas do Administrador (403 para os demais)."""
    if principal.role != ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Ação restrita ao Administrador. Faça login para continuar.",
        )
    return principal


def require_participant(principal: Principal = Depends(get_principal)) -> Principal:
    """Protege as rotas de coleta (notas e questionário): só o login da turma."""
    if not principal.is_participant:
        raise HTTPException(
            status_code=403,
            detail="Entre com o login da turma para registrar avaliações.",
        )
    return principal
