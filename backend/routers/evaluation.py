"""
Avaliação da precisão das respostas.

  - POST /api/evaluations          participante (login da turma) dá nota de 1 a 5 a uma resposta
  - GET  /api/evaluations/summary  🔒 indicadores agregados (nota média, fundamentação…)
  - GET  /api/evaluations/export   🔒 todas as notas em CSV (para análise no TCC)
"""

from collections import Counter, defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from csv_export import csv_response, num, short_id, when
from database import get_db
from dependencies import Principal, require_admin, require_participant
from models import AnswerEvaluation, Interaction
from schemas import EvaluationRequest

router = APIRouter(prefix="/api/evaluations", tags=["avaliação"])

# Notas a partir deste valor contam como "resposta precisa" na taxa de precisão.
PRECISE_MIN_RATING = 4


def _db_unavailable(exc: Exception) -> HTTPException:
    return HTTPException(status_code=503, detail=f"Banco de dados indisponível: {exc}")


def _avg(values) -> Optional[float]:
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 3) if values else None


@router.post("", status_code=201)
def create_evaluation(
    payload: EvaluationRequest,
    principal: Principal = Depends(require_participant),
    db: Session = Depends(get_db),
):
    try:
        interaction = None
        if payload.interaction_id:
            interaction = (
                db.query(Interaction)
                .filter(
                    Interaction.id == payload.interaction_id,
                    Interaction.session_id == principal.session_id,
                )
                .first()
            )

        # Uma nota por pergunta registrada: avaliar de novo substitui a anterior.
        record = None
        if interaction:
            record = (
                db.query(AnswerEvaluation)
                .filter(AnswerEvaluation.interaction_id == interaction.id)
                .first()
            )
        if record is None:
            record = AnswerEvaluation(session_id=principal.session_id)
            db.add(record)

        if interaction:
            record.interaction_id = interaction.id
            record.question = interaction.question
            record.standalone_question = interaction.standalone_question
            record.answer = interaction.answer
            record.scope = interaction.scope
            record.sources = interaction.sources
            record.used_memory = (interaction.memory_mode or "none") != "none"
            record.groundedness = interaction.groundedness
            record.question_coverage = interaction.question_coverage
            record.level = interaction.level
            record.llm_model = interaction.llm_model
        else:
            record.question = payload.question.strip()
            record.standalone_question = (payload.standalone_question or "").strip() or None
            record.answer = payload.answer.strip()
            record.scope = payload.scope
            record.sources = [
                {"folder": s.get("folder"), "source": s.get("source"), "location": s.get("location")}
                for s in payload.sources
                if isinstance(s, dict)
            ]
            record.used_memory = payload.used_memory
            record.groundedness = payload.metrics.groundedness
            record.question_coverage = payload.metrics.question_coverage
            record.level = payload.metrics.level
            record.llm_model = payload.model

        record.rating = payload.rating
        record.comment = (payload.comment or "").strip() or None
        db.commit()
    except Exception as exc:
        db.rollback()
        raise _db_unavailable(exc) from exc
    return {"id": str(record.id), "saved": True}


@router.get("/summary", dependencies=[Depends(require_admin)])
def evaluation_summary(db: Session = Depends(get_db)):
    try:
        rows = db.query(AnswerEvaluation).order_by(AnswerEvaluation.created_at.desc()).all()
    except Exception as exc:
        raise _db_unavailable(exc) from exc

    total = len(rows)
    dist = Counter(r.rating for r in rows)
    levels = Counter(r.level or "indefinido" for r in rows)

    by_model = defaultdict(list)
    for r in rows:
        by_model[r.llm_model or "?"].append(r)

    return {
        "total": total,
        "rating_avg": _avg(r.rating for r in rows),
        "precise_rate": round(sum(1 for r in rows if r.rating >= PRECISE_MIN_RATING) / total, 3)
        if total
        else None,
        "rating_distribution": {str(n): dist.get(n, 0) for n in range(1, 6)},
        "groundedness_avg": _avg(r.groundedness for r in rows),
        "question_coverage_avg": _avg(r.question_coverage for r in rows),
        "levels": {k: levels.get(k, 0) for k in ("alta", "media", "baixa", "indefinido", "acervo")},
        "with_memory": sum(1 for r in rows if r.used_memory),
        "by_model": [
            {
                "model": model,
                "total": len(items),
                "rating_avg": _avg(r.rating for r in items),
                "groundedness_avg": _avg(r.groundedness for r in items),
            }
            for model, items in sorted(by_model.items())
        ],
        "recent_comments": [
            {
                "rating": r.rating,
                "comment": r.comment,
                "question": r.question,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
            if r.comment
        ][:10],
    }


@router.get("/export", dependencies=[Depends(require_admin)])
def export_evaluations(db: Session = Depends(get_db)):
    try:
        rows = db.query(AnswerEvaluation).order_by(AnswerEvaluation.created_at).all()
    except Exception as exc:
        raise _db_unavailable(exc) from exc

    header = [
        "data_utc", "sessao", "modelo", "nota", "comentario", "pergunta", "pergunta_reescrita",
        "usou_memoria", "escopo", "fundamentacao", "cobertura_pergunta", "nivel",
        "artigos", "resposta",
    ]
    data = (
        [
            when(r.created_at),
            short_id(r.session_id),
            r.llm_model or "",
            r.rating,
            r.comment or "",
            r.question,
            r.standalone_question or "",
            "sim" if r.used_memory else "nao",
            r.scope or "",
            num(r.groundedness),
            num(r.question_coverage),
            r.level or "",
            " | ".join(s.get("source", "") for s in (r.sources or [])),
            r.answer,
        ]
        for r in rows
    )
    return csv_response(header, data, "avaliacoes-respostas.csv")
