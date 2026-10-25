"""
Login dos perfis Participante (login da turma) e Administrador.

  - POST /api/auth/login   {username, password} -> {token, role}
  - GET  /api/auth/me      perfil do token atual (a interface confere ao abrir)
  - POST /api/auth/logout  encerra a sessão do participante
"""

import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from config import ADMIN_PASSWORD, ADMIN_USER, PARTICIPANT_PASSWORD, PARTICIPANT_USER
from database import get_db
from dependencies import ADMIN, ADMIN_TOKEN, PARTICIPANTE, Principal, get_principal
from models import ParticipantSession
from schemas import LoginRequest

router = APIRouter(prefix="/api/auth", tags=["login"])


def _matches(given: str, expected: str) -> bool:
    return secrets.compare_digest(given.encode("utf-8"), expected.encode("utf-8"))


def _check(username: str, password: str, user: str, expected_password: str, env_name: str) -> bool:
    """Confere usuário e senha. Senha não definida no .env = login desativado."""
    if not _matches(username, user.lower()):
        return False
    if not expected_password:
        raise HTTPException(
            status_code=503,
            detail=f"Este login não está configurado no servidor: defina {env_name} no arquivo .env.",
        )
    return _matches(password, expected_password)


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    username = (payload.username or "").strip().lower()
    password = payload.password or ""

    if _check(username, password, ADMIN_USER, ADMIN_PASSWORD, "ADMIN_PASSWORD"):
        return {"token": ADMIN_TOKEN, "role": ADMIN}

    if _check(username, password, PARTICIPANT_USER, PARTICIPANT_PASSWORD, "PARTICIPANT_PASSWORD"):
        # A coleta depende do banco: sem ele, o login falha em vez de deixar o
        # participante usar o sistema sem que nada seja registrado.
        session = ParticipantSession(token=secrets.token_urlsafe(32), username=username)
        try:
            db.add(session)
            db.commit()
        except Exception as exc:
            db.rollback()
            raise HTTPException(
                status_code=503,
                detail=f"Banco de dados indisponível: o registro da pesquisa não funcionaria. {exc}",
            ) from exc
        return {"token": session.token, "role": PARTICIPANTE, "session_id": str(session.id)}

    raise HTTPException(status_code=401, detail="Usuário ou senha incorretos.")


@router.get("/me")
def me(principal: Principal = Depends(get_principal)):
    return {"role": principal.role}


@router.post("/logout")
def logout(principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    if principal.is_participant:
        try:
            db.query(ParticipantSession).filter(ParticipantSession.id == principal.session_id).update(
                {"ended_at": datetime.utcnow()}
            )
            db.commit()
        except Exception as exc:
            db.rollback()
            print(f"[WARNING] Falha ao encerrar a sessão do participante: {exc}")
    return {"ok": True}
