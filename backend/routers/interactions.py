"""
Perguntas coletadas com o login da turma.

  - GET /api/interactions/summary  🔒 totais da coleta (sessões, perguntas, avaliações)
  - GET /api/interactions/export   🔒 todas as perguntas e respostas em CSV, com a nota dada
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from csv_export import csv_response, num, short_id, when
from database import get_db
from dependencies import require_admin
from models import AnswerEvaluation, Interaction, ParticipantSession, SurveyResponse

router = APIRouter(prefix="/api/interactions", tags=["coleta"], dependencies=[Depends(require_admin)])


def _db_unavailable(exc: Exception) -> HTTPException:
    return HTTPException(status_code=503, detail=f"Banco de dados indisponível: {exc}")


@router.get("/summary")
def collection_summary(db: Session = Depends(get_db)):
    try:
        sessions = db.query(func.count(ParticipantSession.id)).scalar()
        active = db.query(func.count(func.distinct(Interaction.session_id))).scalar()
        questions = db.query(func.count(Interaction.id)).scalar()
        rated = db.query(func.count(AnswerEvaluation.interaction_id)).scalar()
        surveys = db.query(func.count(SurveyResponse.id)).scalar()
        avg_ms: Optional[float] = db.query(func.avg(Interaction.response_ms)).scalar()
    except Exception as exc:
        raise _db_unavailable(exc) from exc
    return {
        "sessoes": sessions,
        "sessoes_com_perguntas": active,
        "perguntas": questions,
        "perguntas_avaliadas": rated,
        "questionarios": surveys,
        "tempo_medio_s": round(float(avg_ms) / 1000, 1) if avg_ms is not None else None,
    }


@router.get("/export")
def export_interactions(db: Session = Depends(get_db)):
    try:
        rows = (
            db.query(Interaction, AnswerEvaluation)
            .outerjoin(AnswerEvaluation, AnswerEvaluation.interaction_id == Interaction.id)
            .order_by(Interaction.created_at)
            .all()
        )
    except Exception as exc:
        raise _db_unavailable(exc) from exc

    header = [
        "data_utc", "sessao", "modelo", "pergunta", "pergunta_buscada", "memoria", "escopo",
        "tempo_s", "fundamentacao", "cobertura_pergunta", "nivel", "nota", "comentario_nota",
        "artigos", "resposta",
    ]
    data = (
        [
            when(i.created_at),
            short_id(i.session_id),
            i.llm_model or "",
            i.question,
            i.standalone_question or "",
            i.memory_mode or "",
            i.scope or "",
            num(i.response_ms / 1000, 1) if i.response_ms is not None else "",
            num(i.groundedness),
            num(i.question_coverage),
            i.level or "",
            e.rating if e else "",
            (e.comment or "") if e else "",
            " | ".join(s.get("source", "") for s in (i.sources or [])),
            i.answer,
        ]
        for i, e in rows
    )
    return csv_response(header, data, "perguntas-coletadas.csv")
