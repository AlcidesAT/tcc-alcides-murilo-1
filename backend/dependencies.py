"""
Dependências compartilhadas pelas rotas da API.

  - `get_rag()`: instância única do pipeline RAG (criada na primeira chamada).
  - `require_admin`: protege as rotas exclusivas do perfil Administrador.
"""

import secrets
from functools import lru_cache
from typing import Optional

from fastapi import Header, HTTPException

from rag import RAGService

# Token de sessão do administrador, gerado a cada inicialização do servidor.
# Quem informar a senha correta recebe este token e o reenvia no cabeçalho
# `X-Admin-Token` para acessar as rotas de gestão (upload, criação/remoção).
ADMIN_TOKEN = secrets.token_urlsafe(32)


@lru_cache(maxsize=1)
def get_rag() -> RAGService:
    return RAGService()


def require_admin(x_admin_token: Optional[str] = Header(default=None)):
    """Dependência que protege as rotas exclusivas do Administrador.

    O perfil Leitor (sem token) recebe 403 ao tentar enviar ou gerenciar
    artigos. A comparação usa `secrets.compare_digest` para evitar timing.
    """
    if not x_admin_token or not secrets.compare_digest(x_admin_token, ADMIN_TOKEN):
        raise HTTPException(
            status_code=403,
            detail="Ação restrita ao Administrador. Faça login para continuar.",
        )
