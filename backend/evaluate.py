"""
Avaliação offline da precisão do sistema RAG (benchmark).

Lê um conjunto de perguntas com os artigos que deveriam fundamentar cada
resposta (`data/evaluation/perguntas.json`) e mede:

  Recuperação (sempre):
    - Acerto@K: algum artigo esperado aparece entre os K trechos recuperados?
    - MRR: média de 1/posição do primeiro trecho de um artigo esperado.
    - Precisão das referências: fração das referências exibidas ao usuário
      que são artigos esperados.
    - Revocação das referências: fração dos artigos esperados que foram exibidos.

  Memória de pergunta (itens com "historico"):
    - Compara o Acerto@K da pergunta de acompanhamento SEM memória (pergunta
      crua) e COM memória (pergunta reescrita a partir do histórico).

  Geração (opcional, com --gerar; bem mais lento):
    - Fundamentação média das respostas nos trechos (rag/evaluation.py),
      distribuição dos níveis de confiança e tempo médio por resposta.

Os resultados vão para o console e para um JSON em
`data/evaluation/resultados/`, junto dos parâmetros usados (modelo, K, MMR...),
para comparar execuções com configurações diferentes.

Pré-requisito: Ollama em execução (embeddings; o LLM é usado para reescrever
perguntas com histórico e, com --gerar, para responder).

Uso (a partir da pasta `backend`):
    python evaluate.py
    python evaluate.py --gerar
    python evaluate.py --arquivo ../data/evaluation/perguntas.json
"""

import argparse
import json
import time
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from config import (
    EMBEDDING_MODEL,
    EVALUATION_DIR,
    LLM_MODEL,
    MEMORY_MAX_TURNS,
    MMR_FETCH_K,
    MMR_LAMBDA,
    REFERENCES_MAX,
    REFERENCES_MIN_RATIO,
    RETRIEVAL_K,
    slugify_folder,
)
from rag import RAGService


def _norm(name: str) -> str:
    return unicodedata.normalize("NFC", name or "").strip().casefold()


def _first_hit_rank(docs, expected: set) -> Optional[int]:
    for rank, d in enumerate(docs, start=1):
        if _norm(d.metadata.get("source")) in expected:
            return rank
    return None


def _mean(values) -> Optional[float]:
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def _fmt(v: Optional[float], pct: bool = True) -> str:
    if v is None:
        return "—"
    return f"{v * 100:.1f}%" if pct else f"{v:.3f}"


def evaluate_item(rag: RAGService, item: Dict, generate: bool) -> Dict:
    expected = {_norm(a) for a in item["artigos_esperados"]}
    folder = slugify_folder(item["assunto"]) if item.get("assunto") else None
    history = [
        {"question": h.get("pergunta", ""), "answer": h.get("resposta", "")}
        for h in item.get("historico", [])
    ]

    t0 = time.perf_counter()
    ctx = rag.prepare(item["pergunta"], folder, None, history)
    retrieval_s = time.perf_counter() - t0

    rank = _first_hit_rank(ctx.docs, expected)
    shown = [_norm(s["source"]) for s in ctx.sources]
    hits_shown = sum(1 for s in shown if s in expected)

    result = {
        "id": item.get("id"),
        "pergunta": item["pergunta"],
        "pergunta_busca": ctx.standalone_question,
        "modo_memoria": ctx.resolution.mode,
        "consultas": ctx.resolution.queries,
        "artigos_esperados": item["artigos_esperados"],
        "artigos_recuperados": list(dict.fromkeys(d.metadata.get("source") for d in ctx.docs)),
        "referencias": [s["source"] for s in ctx.sources],
        "acerto": rank is not None,
        "posicao": rank,
        "rr": (1 / rank) if rank else 0.0,
        "precisao_refs": (hits_shown / len(shown)) if shown else 0.0,
        "revocacao_refs": len(expected & set(shown)) / len(expected),
        "tempo_recuperacao_s": round(retrieval_s, 2),
    }

    if history:
        # Mesma pergunta sem a memória: mostra o quanto a reescrita ajuda.
        raw_docs = rag.retriever.retrieve(item["pergunta"], folder, None)
        result["acerto_sem_memoria"] = _first_hit_rank(raw_docs, expected) is not None

    if generate:
        t1 = time.perf_counter()
        answer = rag.generate(ctx)
        result["tempo_geracao_s"] = round(time.perf_counter() - t1, 2)
        result["resposta"] = answer
        result["avaliacao"] = rag.evaluate(ctx, answer)

    return result


def summarize(results: List[Dict], generate: bool) -> Dict:
    n = len(results)
    summary = {
        "perguntas": n,
        "acerto_k": sum(r["acerto"] for r in results) / n,
        "mrr": _mean(r["rr"] for r in results),
        "precisao_referencias": _mean(r["precisao_refs"] for r in results),
        "revocacao_referencias": _mean(r["revocacao_refs"] for r in results),
        "tempo_medio_recuperacao_s": _mean(r["tempo_recuperacao_s"] for r in results),
    }

    mem = [r for r in results if "acerto_sem_memoria" in r]
    if mem:
        summary["memoria"] = {
            "perguntas": len(mem),
            "acerto_sem_memoria": sum(r["acerto_sem_memoria"] for r in mem) / len(mem),
            "acerto_com_memoria": sum(r["acerto"] for r in mem) / len(mem),
        }

    if generate:
        evals = [r["avaliacao"] for r in results]
        summary["geracao"] = {
            "fundamentacao_media": _mean(e["groundedness"] for e in evals),
            "cobertura_media": _mean(e["question_coverage"] for e in evals),
            "niveis": dict(Counter(e["level"] for e in evals)),
            "tempo_medio_geracao_s": _mean(r["tempo_geracao_s"] for r in results),
        }
    return summary


def print_report(results: List[Dict], summary: Dict) -> None:
    print("\n" + "=" * 78)
    print(f"  Avaliação do RAG — modelo {LLM_MODEL}, K={RETRIEVAL_K}, MMR lambda={MMR_LAMBDA}")
    print("=" * 78)
    for r in results:
        status = f"acerto (pos. {r['posicao']})" if r["acerto"] else "ERRO"
        line = f"[{r['id']}] {status:<16} refs: {_fmt(r['precisao_refs'])} precisão"
        if "acerto_sem_memoria" in r:
            line += f" | sem memória: {'acerto' if r['acerto_sem_memoria'] else 'ERRO'}"
        if "avaliacao" in r:
            line += f" | fundamentação {_fmt(r['avaliacao']['groundedness'])}"
        print(line)
        if r["modo_memoria"] != "none":
            print(f"        memória ({r['modo_memoria']}): {r['pergunta_busca']}")
        if not r["acerto"]:
            print(f"        recuperados: {', '.join(r['artigos_recuperados'][:3])}")

    print("-" * 78)
    print(f"Perguntas ............................ {summary['perguntas']}")
    print(f"Acerto@{RETRIEVAL_K} ............................. {_fmt(summary['acerto_k'])}")
    print(f"MRR .................................. {_fmt(summary['mrr'], pct=False)}")
    print(f"Precisão das referências ............. {_fmt(summary['precisao_referencias'])}")
    print(f"Revocação das referências ............ {_fmt(summary['revocacao_referencias'])}")
    if "memoria" in summary:
        m = summary["memoria"]
        print(
            f"Memória ({m['perguntas']} perguntas de acompanhamento): "
            f"acerto sem memória {_fmt(m['acerto_sem_memoria'])} -> "
            f"com memória {_fmt(m['acerto_com_memoria'])}"
        )
    if "geracao" in summary:
        g = summary["geracao"]
        print(f"Fundamentação média das respostas .... {_fmt(g['fundamentacao_media'])}")
        print(f"Níveis de confiança .................. {g['niveis']}")
        print(f"Tempo médio de geração ............... {g['tempo_medio_geracao_s']:.1f} s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Avaliação offline da precisão do RAG.")
    parser.add_argument(
        "--arquivo",
        default=str(EVALUATION_DIR / "perguntas.json"),
        help="JSON com as perguntas de referência.",
    )
    parser.add_argument(
        "--gerar",
        action="store_true",
        help="Também gera as respostas e mede a fundamentação (lento).",
    )
    parser.add_argument(
        "--saida",
        default=str(EVALUATION_DIR / "resultados"),
        help="Pasta onde o JSON com os resultados é salvo.",
    )
    args = parser.parse_args()

    with open(args.arquivo, encoding="utf-8") as f:
        items = json.load(f)["perguntas"]

    print("[INFO] Inicializando pipeline RAG (requer o Ollama em execução)...")
    rag = RAGService()

    indexed = {_norm(d["source"]) for d in rag.list_documents()}
    for item in items:
        missing = [a for a in item["artigos_esperados"] if _norm(a) not in indexed]
        if missing:
            print(f"[AVISO] {item.get('id')}: artigo(s) esperado(s) não indexado(s): {missing}")

    results = []
    for i, item in enumerate(items, start=1):
        print(f"[{i}/{len(items)}] {item.get('id')}: {item['pergunta']}")
        results.append(evaluate_item(rag, item, args.gerar))

    summary = summarize(results, args.gerar)
    print_report(results, summary)

    out_dir = Path(args.saida)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"avaliacao-{datetime.now():%Y%m%d-%H%M%S}.json"
    with out_file.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "executado_em": datetime.now().isoformat(timespec="seconds"),
                "parametros": {
                    "llm_model": LLM_MODEL,
                    "embedding_model": EMBEDDING_MODEL,
                    "retrieval_k": RETRIEVAL_K,
                    "mmr_fetch_k": MMR_FETCH_K,
                    "mmr_lambda": MMR_LAMBDA,
                    "references_max": REFERENCES_MAX,
                    "references_min_ratio": REFERENCES_MIN_RATIO,
                    "memory_max_turns": MEMORY_MAX_TURNS,
                    "gerou_respostas": args.gerar,
                },
                "resumo": summary,
                "resultados": results,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"\nResultados salvos em {out_file}")


if __name__ == "__main__":
    main()
