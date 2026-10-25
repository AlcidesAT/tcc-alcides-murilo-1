"""
Gravações "best-effort" no PostgreSQL feitas durante as respostas.

Qualquer falha (banco indisponível, etc.) é apenas registrada no console e
nunca interrompe a resposta ao usuário.
"""

from typing import Dict, Optional

from database import SessionLocal
from models import Interaction, QuestionSource


def save_interaction(session_id, question: str, result: Dict, response_ms: int) -> Optional[str]:
    """Registra a pergunta de um participante e a resposta gerada.

    `result` é o dicionário de `RAGService.result()` (com "answer"). Devolve o
    id da pergunta registrada, ou None se o banco falhar — a resposta ao
    participante segue normalmente.
    """
    try:
        db = SessionLocal()
    except Exception as exc:
        print(f"[WARNING] Não foi possível abrir sessão do banco: {exc}")
        return None

    try:
        evaluation = result.get("evaluation") or {}
        record = Interaction(
            session_id=session_id,
            question=question,
            standalone_question=result.get("standalone_question"),
            answer=result.get("answer", ""),
            scope=result.get("scope"),
            sources=[
                {"folder": s.get("folder"), "source": s.get("source"), "location": s.get("location")}
                for s in result.get("sources") or []
            ],
            memory_mode=result.get("memory_mode"),
            groundedness=evaluation.get("groundedness"),
            question_coverage=evaluation.get("question_coverage"),
            level=evaluation.get("level"),
            llm_model=result.get("model"),
            response_ms=response_ms,
        )
        db.add(record)
        db.commit()
        return str(record.id)
    except Exception as exc:
        print(f"[WARNING] Falha ao registrar a pergunta do participante: {exc}")
        try:
            db.rollback()
        except Exception:
            pass
        return None
    finally:
        db.close()


def save_sources(sources: list) -> None:
    """Persiste, um registro por artigo distinto, as fontes usadas numa resposta."""
    try:
        db = SessionLocal()
    except Exception as exc:
        print(f"[WARNING] Não foi possível abrir sessão do banco: {exc}")
        return

    try:
        grouped: dict = {}
        for s in sources:
            key = (s.get("folder"), s.get("source"))
            entry = grouped.setdefault(key, {"locations": [], "snippet": s.get("snippet", "")})
            loc = s.get("location")
            if loc and loc not in entry["locations"]:
                entry["locations"].append(loc)

        for (fld, art), info in grouped.items():
            db.add(
                QuestionSource(
                    folder=fld,
                    article=art,
                    locations=", ".join(info["locations"]),
                    snippet=info["snippet"],
                )
            )
        db.commit()
    except Exception as exc:
        print(f"[WARNING] Falha ao salvar fontes no banco: {exc}")
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()
