"""
Dependências compartilhadas pelas rotas da API.

  - `get_rag()`: instância única do pipeline RAG (criada na primeira chamada).
  - `get_principal`: quem está fazendo a requisição (leitor ou admin).
  - `require_admin`: protege as rotas do Administrador.

O navegador envia o token recebido no login no cabeçalho `X-Auth-Token`.
"""

import secrets
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from fastapi import Depends, Header, HTTPException

from rag import RAGService

# Token de sessão do administrador, gerado a cada inicialização do servidor.
ADMIN_TOKEN = secrets.token_urlsafe(32)

LEITOR, ADMIN = "leitor", "admin"


@dataclass
class Principal:
    role: str


@lru_cache(maxsize=1)
def get_rag() -> RAGService:
    return RAGService()


def get_principal(x_auth_token: Optional[str] = Header(default=None)) -> Principal:
    """Resolve o perfil pelo token. Sem token (ou token inválido): Leitor."""
    if x_auth_token and secrets.compare_digest(x_auth_token, ADMIN_TOKEN):
        return Principal(ADMIN)
    return Principal(LEITOR)


def require_admin(principal: Principal = Depends(get_principal)) -> Principal:
    """Protege as rotas exclusivas do Administrador (403 para os demais)."""
    if principal.role != ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Ação restrita ao Administrador. Faça login para continuar.",
        )
    return principal
