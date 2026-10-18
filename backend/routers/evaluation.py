"""
Avaliação da precisão das respostas.

  - POST /api/evaluations          qualquer perfil registra a nota (1 a 5) de uma resposta
  - GET  /api/evaluations/summary  🔒 indicadores agregados (nota média, fundamentação…)
  - GET  /api/evaluations/export   🔒 todas as avaliações em CSV (para análise no TCC)
"""

import csv
import io
from collections import Counter, defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from database import get_db
from dependencies import require_admin
from models import AnswerEvaluation
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
def create_evaluation(payload: EvaluationRequest, db: Session = Depends(get_db)):
    sources = [
        {
            "folder": s.get("folder"),
            "source": s.get("source"),
            "location": s.get("location"),
        }
        for s in payload.sources
        if isinstance(s, dict)
    ]
    record = AnswerEvaluation(
        question=payload.question.strip(),
        standalone_question=(payload.standalone_question or "").strip() or None,
        answer=payload.answer.strip(),
        scope=payload.scope,
        sources=sources,
        used_memory=payload.used_memory,
        rating=payload.rating,
        comment=(payload.comment or "").strip() or None,
        groundedness=payload.metrics.groundedness,
        question_coverage=payload.metrics.question_coverage,
        level=payload.metrics.level,
        llm_model=payload.model,
    )
    try:
        db.add(record)
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
    """CSV separado por ';' com BOM UTF-8 (abre direto no Excel em pt-BR)."""
    try:
        rows = db.query(AnswerEvaluation).order_by(AnswerEvaluation.created_at).all()
    except Exception as exc:
        raise _db_unavailable(exc) from exc

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(
        [
            "data_utc", "modelo", "nota", "comentario", "pergunta", "pergunta_reescrita",
            "usou_memoria", "escopo", "fundamentacao", "cobertura_pergunta", "nivel",
            "artigos", "resposta",
        ]
    )
    for r in rows:
        writer.writerow(
            [
                r.created_at.isoformat(sep=" ", timespec="seconds") if r.created_at else "",
                r.llm_model or "",
                r.rating,
                r.comment or "",
                r.question,
                r.standalone_question or "",
                "sim" if r.used_memory else "nao",
                r.scope or "",
                "" if r.groundedness is None else f"{r.groundedness:.3f}".replace(".", ","),
                "" if r.question_coverage is None else f"{r.question_coverage:.3f}".replace(".", ","),
                r.level or "",
                " | ".join(s.get("source", "") for s in (r.sources or [])),
                r.answer,
            ]
        )

    return Response(
        content="﻿" + buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="avaliacoes-respostas.csv"'},
    )
