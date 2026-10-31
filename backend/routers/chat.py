"""
Perguntas em linguagem natural (com memória da conversa).
"""

import json
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import iterate_in_threadpool, run_in_threadpool
from fastapi.responses import StreamingResponse

from config import LLM_MAX_CONCURRENT, QUEUE_UPDATE_SECONDS, REQUIRE_LOGIN, slugify_folder
from dependencies import LEITOR, Principal, get_principal, get_rag
from persistence import save_interaction, save_sources, session_quota
from rag import RAGContext, RAGService
from rag.queue import GenerationQueue
from schemas import AskRequest, AskResponse

router = APIRouter(prefix="/api", tags=["perguntas"])

OLLAMA_HINT = "Verifique se o Ollama está em execução e se os modelos foram baixados."

generation_queue = GenerationQueue(LLM_MAX_CONCURRENT)


def _authorize(principal: Principal) -> None:
    """Regras da coleta: login obrigatório (opcional) e limite por sessão.

    A pergunta só conta depois de respondida e registrada: resposta com erro
    não consome o limite.
    """
    if REQUIRE_LOGIN and principal.role == LEITOR:
        raise HTTPException(status_code=401, detail="Entre com o login da turma para fazer perguntas.")
    if not principal.is_participant:
        return
    quota = session_quota(principal.session_id)
    limit = quota["questions_limit"]
    if limit and quota["questions_used"] >= limit:
        raise HTTPException(
            status_code=403,
            detail=f"Você já fez as {limit} perguntas desta sessão. Responda ao questionário de avaliação.",
        )


def _validate_ask(payload: AskRequest, rag: RAGService):
    """Valida a pergunta e o escopo; devolve (question, folder_slug, source)."""
    question = (payload.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Pergunta vazia.")

    folders = rag.lexical.folders()
    if not folders:
        raise HTTPException(
            status_code=400,
            detail="Nenhum artigo indexado. Envie pelo menos um documento antes de perguntar.",
        )

    folder_slug = slugify_folder(payload.folder) if payload.folder else None
    if folder_slug and folder_slug not in folders:
        raise HTTPException(status_code=404, detail=f"Pasta '{folder_slug}' não existe.")

    source = (payload.source or "").strip() or None
    return question, folder_slug, source


def _prepare(payload: AskRequest, rag: RAGService, rewrite: bool = True) -> RAGContext:
    question, folder_slug, source = _validate_ask(payload, rag)
    try:
        return rag.prepare(question, folder_slug, source, payload.history, rewrite)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Falha ao recuperar trechos. {OLLAMA_HINT} Detalhe: {exc}",
        ) from exc


def _collect(principal: Principal, ctx: RAGContext, result: dict, started: float) -> dict:
    """Com o login da turma, registra a pergunta e a resposta no banco."""
    if not principal.is_participant:
        return {"interaction_id": None, "collected": False}
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    interaction_id = save_interaction(principal.session_id, ctx.question, result, elapsed_ms)
    return {
        "interaction_id": interaction_id,
        "collected": interaction_id is not None,
        **session_quota(principal.session_id),
    }


@router.post("/ask", response_model=AskResponse)
async def ask(
    payload: AskRequest,
    rag: RAGService = Depends(get_rag),
    principal: Principal = Depends(get_principal),
):
    started = time.perf_counter()
    await run_in_threadpool(_authorize, principal)
    ctx = await run_in_threadpool(_prepare, payload, rag, False)

    ticket = generation_queue.join() if ctx.needs_model else None
    completed = False
    try:
        if ticket:
            await ticket.turn.wait()
        if ctx.rewrite_pending:
            ctx = await run_in_threadpool(_prepare, payload, rag)
        answer = await run_in_threadpool(rag.generate, ctx)
        completed = True
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Falha ao gerar resposta. {OLLAMA_HINT} Detalhe: {exc}",
        ) from exc
    finally:
        if ticket:
            generation_queue.leave(ticket, completed)

    await run_in_threadpool(save_sources, ctx.sources)
    result = await run_in_threadpool(rag.result, ctx, answer)
    collected = await run_in_threadpool(_collect, principal, ctx, result, started)
    return {**result, **collected}


def _event(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False) + "\n"


@router.post("/ask/stream")
async def ask_stream(
    payload: AskRequest,
    rag: RAGService = Depends(get_rag),
    principal: Principal = Depends(get_principal),
):
    """Versão em streaming: emite NDJSON (uma linha JSON por evento).

    Eventos, em ordem:
      {"type":"sources","sources":[...],"scope":...}  (na hora, sem esperar o modelo)
      {"type":"queue","position":...,"eta_seconds":...}  (enquanto espera a vez)
      {"type":"meta", "standalone_question", "used_memory", "memory_turns", ...}
      {"type":"token","text":...}  (vários, durante a geração)
      {"type":"done","sources":[...],"scope":...,"evaluation":{...},"model":...,
       "interaction_id":..., "collected":..., "questions_used":..., "questions_limit":...}
    Erros durante a geração viram {"type":"error","detail":...}. Com o login da
    turma, a pergunta é registrada antes do evento "done" (que leva o id).
    """
    started = time.perf_counter()
    await run_in_threadpool(_authorize, principal)
    # Memória + recuperação acontecem antes do streaming para que falhas (ex.:
    # Ollama indisponível ao gerar embeddings) retornem um status HTTP adequado.
    # Sem o LLM, elas não dependem da fila.
    first = await run_in_threadpool(_prepare, payload, rag, False)

    async def generate():
        ctx = first
        yield _event({"type": "sources", "sources": ctx.sources, "scope": ctx.scope})

        parts = []
        ticket = generation_queue.join() if ctx.needs_model else None
        completed = False
        try:
            # A atualização periódica também revela quem desistiu: o envio falha
            # e o `finally` tira a pergunta da fila, sem gastar o modelo com ela.
            while ticket and not ticket.turn.is_set():
                yield _event({"type": "queue", **generation_queue.status(ticket)})
                await generation_queue.wait(ticket, QUEUE_UPDATE_SECONDS)

            if ctx.rewrite_pending:
                ctx = await run_in_threadpool(_prepare, payload, rag)
            yield _event({"type": "meta", **ctx.meta()})

            tokens = rag.stream_answer(ctx)
            try:
                async for token in iterate_in_threadpool(tokens):
                    parts.append(token)
                    yield _event({"type": "token", "text": token})
            finally:
                tokens.close()
            completed = True
        except HTTPException as exc:
            yield _event({"type": "error", "detail": exc.detail})
            return
        except Exception as exc:
            yield _event({"type": "error", "detail": str(exc)})
            return
        finally:
            if ticket:
                generation_queue.leave(ticket, completed)

        result = await run_in_threadpool(rag.result, ctx, "".join(parts))
        collected = await run_in_threadpool(_collect, principal, ctx, result, started)
        result.pop("answer")  # o texto já foi enviado token a token
        yield _event({"type": "done", **result, **collected})

        await run_in_threadpool(save_sources, ctx.sources)

    return StreamingResponse(generate(), media_type="application/x-ndjson")
