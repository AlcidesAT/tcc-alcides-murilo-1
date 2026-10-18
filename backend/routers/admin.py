"""
Autenticação do perfil Administrador.
"""

import secrets

from fastapi import APIRouter, HTTPException

from config import ADMIN_PASSWORD
from dependencies import ADMIN_TOKEN
from schemas import AdminLoginRequest

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/login")
def admin_login(payload: AdminLoginRequest):
    """Valida a senha do Administrador e devolve o token de sessão."""
    if not secrets.compare_digest(payload.password or "", ADMIN_PASSWORD):
        raise HTTPException(status_code=401, detail="Senha de administrador incorreta.")
    return {"token": ADMIN_TOKEN, "role": "admin"}
