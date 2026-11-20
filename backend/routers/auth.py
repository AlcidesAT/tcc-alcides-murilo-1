"""
Login do Administrador.

  - POST /api/auth/login   {username, password} -> {token, role}
  - GET  /api/auth/me      perfil do token atual
  - POST /api/auth/logout  sair (o token do admin só muda ao reiniciar o servidor)
"""

import secrets

from fastapi import APIRouter, Depends, HTTPException

from config import ADMIN_PASSWORD, ADMIN_USER
from dependencies import ADMIN, ADMIN_TOKEN, Principal, get_principal
from schemas import LoginRequest

router = APIRouter(prefix="/api/auth", tags=["login"])


def _matches(given: str, expected: str) -> bool:
    return secrets.compare_digest(given.encode("utf-8"), expected.encode("utf-8"))


@router.post("/login")
def login(payload: LoginRequest):
    username = (payload.username or "").strip().lower()
    password = payload.password or ""

    if _matches(username, ADMIN_USER.lower()):
        if not ADMIN_PASSWORD:
            raise HTTPException(
                status_code=503,
                detail="Este login não está configurado no servidor: defina ADMIN_PASSWORD no arquivo .env.",
            )
        if _matches(password, ADMIN_PASSWORD):
            return {"token": ADMIN_TOKEN, "role": ADMIN}

    raise HTTPException(status_code=401, detail="Usuário ou senha incorretos.")


@router.get("/me")
def me(principal: Principal = Depends(get_principal)):
    return {"role": principal.role}


@router.post("/logout")
def logout():
    return {"ok": True}
