"""
Questionário de avaliação do sistema, respondido nos testes com a turma.

  - GET /api/survey/summary  🔒 média e distribuição por afirmação, comentários
  - GET /api/survey/export   🔒 uma linha por participante, uma coluna por afirmação

As afirmações ficam em data/evaluation/questionario.json (lidas a cada
requisição, então editar o arquivo não exige reiniciar o servidor).
"""

import json
from collections import Counter
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from config import SURVEY_FILE
from csv_export import csv_response, num, short_id, when
from database import get_db
from dependencies import require_admin
from models import SurveyResponse

router = APIRouter(prefix="/api/survey", tags=["questionário"], dependencies=[Depends(require_admin)])


def load_survey() -> Dict:
    try:
        with open(SURVEY_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Questionário inválido ({SURVEY_FILE}): {exc}") from exc


def _db_unavailable(exc: Exception) -> HTTPException:
    return HTTPException(status_code=503, detail=f"Banco de dados indisponível: {exc}")


def _avg(values) -> Optional[float]:
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 2) if values else None


@router.get("/summary")
def survey_summary(db: Session = Depends(get_db)):
    survey = load_survey()
    try:
        rows = db.query(SurveyResponse).order_by(SurveyResponse.updated_at.desc()).all()
    except Exception as exc:
        raise _db_unavailable(exc) from exc

    items = []
    for item in survey["afirmacoes"]:
        notes = [r.answers.get(item["id"]) for r in rows if r.answers]
        dist = Counter(n for n in notes if n is not None)
        items.append(
            {
                "id": item["id"],
                "criterio": item.get("criterio", item["id"]),
                "texto": item["texto"],
                "media": _avg(notes),
                "distribuicao": {str(n): dist.get(n, 0) for n in range(1, 6)},
            }
        )
    all_notes = [n for r in rows for n in (r.answers or {}).values()]
    return {
        "respondentes": len(rows),
        "media_geral": _avg(all_notes),
        "afirmacoes": items,
        "comentarios": [
            {"comentario": r.comment, "data": when(r.updated_at)} for r in rows if r.comment
        ][:10],
    }


@router.get("/export")
def export_survey(db: Session = Depends(get_db)):
    survey = load_survey()
    ids = [item["id"] for item in survey["afirmacoes"]]
    try:
        rows = db.query(SurveyResponse).order_by(SurveyResponse.created_at).all()
    except Exception as exc:
        raise _db_unavailable(exc) from exc

    header = ["data_utc", "sessao", "versao_questionario", *ids, "media", "comentario"]
    data = []
    for r in rows:
        notes = [(r.answers or {}).get(i) for i in ids]
        data.append(
            [
                when(r.updated_at),
                short_id(r.session_id),
                r.survey_version or "",
                *["" if n is None else n for n in notes],
                num(_avg(notes), 2),
                r.comment or "",
            ]
        )
    return csv_response(header, data, "questionario-avaliacao.csv")
