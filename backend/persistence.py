"""
Gravações "best-effort" no PostgreSQL feitas durante as respostas.

Qualquer falha (banco indisponível, etc.) é apenas registrada no console e
nunca interrompe a resposta ao usuário.
"""

from database import SessionLocal
from models import QuestionSource


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
