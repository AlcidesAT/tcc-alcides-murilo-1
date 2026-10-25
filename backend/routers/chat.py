"""
Perguntas em linguagem natural (com memória da conversa).
"""

import json
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from config import slugify_folder
from dependencies import Principal, get_principal, get_rag
from persistence import save_interaction, save_sources
from rag import RAGContext, RAGService
from schemas import AskRequest, AskResponse

router = APIRouter(prefix="/api", tags=["perguntas"])

OLLAMA_HINT = "Verifique se o Ollama está em execução e se os modelos foram baixados."


def _validate_ask(payload: AskRequest, rag: RAGService):
    """Valida a pergunta e o escopo; devolve (question, folder_slug, source)."""
    question = (payload.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Pergunta vazia.")

    folders = rag.list_folders()
    if not folders:
        raise HTTPException(
            status_code=400,
            detail="Nenhum artigo indexado. Envie pelo menos um documento antes de perguntar.",
        )

    folder_slug = slugify_folder(payload.folder) if payload.folder else None
    if folder_slug and not any(f["folder"] == folder_slug for f in folders):
        raise HTTPException(status_code=404, detail=f"Pasta '{folder_slug}' não existe.")

    source = (payload.source or "").strip() or None
    return question, folder_slug, source


def _prepare(payload: AskRequest, rag: RAGService) -> RAGContext:
    question, folder_slug, source = _validate_ask(payload, rag)
    try:
        return rag.prepare(question, folder_slug, source, payload.history)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Falha ao recuperar trechos. {OLLAMA_HINT} Detalhe: {exc}",
        ) from exc


def _collect(principal: Principal, ctx: RAGContext, result: dict, started: float) -> dict:
    """Com o login da turma, registra a pergunta e a resposta no banco."""
    interaction_id = None
    if principal.is_participant:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        interaction_id = save_interaction(principal.session_id, ctx.question, result, elapsed_ms)
    return {"interaction_id": interaction_id, "collected": interaction_id is not None}


@router.post("/ask", response_model=AskResponse)
def ask(
    payload: AskRequest,
    rag: RAGService = Depends(get_rag),
    principal: Principal = Depends(get_principal),
):
    started = time.perf_counter()
    ctx = _prepare(payload, rag)
    try:
        answer = rag.generate(ctx)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Falha ao gerar resposta. {OLLAMA_HINT} Detalhe: {exc}",
        ) from exc

    save_sources(ctx.sources)
    result = rag.result(ctx, answer)
    return {**result, **_collect(principal, ctx, result, started)}


def _event(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False) + "\n"


@router.post("/ask/stream")
def ask_stream(
    payload: AskRequest,
    rag: RAGService = Depends(get_rag),
    principal: Principal = Depends(get_principal),
):
    """Versão em streaming: emite NDJSON (uma linha JSON por evento).

    Eventos, em ordem:
      {"type":"meta", "standalone_question", "used_memory", "memory_turns", ...}
      {"type":"token","text":...}  (vários, durante a geração)
      {"type":"done","sources":[...],"scope":...,"evaluation":{...},"model":...,
       "interaction_id":..., "collected":...}
    Erros durante a geração viram {"type":"error","detail":...}. Com o login da
    turma, a pergunta é registrada antes do evento "done" (que leva o id).
    """
    started = time.perf_counter()
    # Memória + recuperação acontecem antes do streaming para que falhas (ex.:
    # Ollama indisponível ao gerar embeddings) retornem um status HTTP adequado.
    ctx = _prepare(payload, rag)

    def generate():
        yield _event({"type": "meta", **ctx.meta()})

        parts = []
        try:
            for token in rag.stream_answer(ctx):
                parts.append(token)
                yield _event({"type": "token", "text": token})
        except Exception as exc:
            yield _event({"type": "error", "detail": str(exc)})
            return

        result = rag.result(ctx, "".join(parts))
        collected = _collect(principal, ctx, result, started)
        result.pop("answer")  # o texto já foi enviado token a token
        yield _event({"type": "done", **result, **collected})

        save_sources(ctx.sources)

    return StreamingResponse(generate(), media_type="application/x-ndjson")
