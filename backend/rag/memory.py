"""
Memória de pergunta (memória da conversa).

O backend continua sem estado: a interface envia, junto de cada pergunta, os
últimos pares pergunta/resposta da conversa. Aqui esse histórico é:

  1. normalizado (no máximo `MEMORY_MAX_TURNS` pares, respostas cortadas em
     `MEMORY_ANSWER_CHARS`);
  2. usado para resolver perguntas de ACOMPANHAMENTO — as que dependem da
     conversa para fazer sentido ("e a metodologia?", "quais limitações
     encontraram nelas?"). Perguntas completas seguem intactas;
  3. incluído no prompt de geração, para que o modelo entenda a que a pergunta
     se refere.

Resolução de uma pergunta de acompanhamento:

  a. o LLM reescreve a pergunta incorporando o tema do histórico;
  b. a reescrita só é aceita se trouxer algum termo específico do histórico
     (modelos pequenos às vezes "perdem" o assunto ou inventam outro);
  c. a busca usa DUAS consultas, fundidas por RRF: a reescrita e a expansão
     determinística "pergunta anterior + pergunta atual", que garante que os
     termos do tema nunca se percam.
"""

import re
from dataclasses import dataclass, field
from typing import Iterable, List

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from config import MEMORY_ANSWER_CHARS, MEMORY_MAX_TURNS
from rag.lexical import stem, tokenize, words
from rag.prompts import CONDENSE_PROMPT


@dataclass
class Turn:
    question: str
    answer: str


@dataclass
class Resolution:
    """Como a pergunta foi entendida com a ajuda da memória.

    `mode`: "none" (pergunta completa, memória não aplicada), "rewrite"
    (reescrita do LLM aceita) ou "expansion" (reescrita rejeitada; busca com a
    pergunta anterior + a atual).
    """

    standalone: str  # pergunta completa usada na busca/avaliação
    queries: List[str] = field(default_factory=list)  # consultas fundidas na busca
    mode: str = "none"

    @property
    def follow_up(self) -> bool:
        return self.mode != "none"


def normalize_history(raw: Iterable) -> List[Turn]:
    """Converte o histórico recebido (dicts ou objetos) em `Turn`s enxutos."""
    turns: List[Turn] = []
    for item in raw or []:
        q = item.get("question") if isinstance(item, dict) else getattr(item, "question", "")
        a = item.get("answer") if isinstance(item, dict) else getattr(item, "answer", "")
        q, a = (q or "").strip(), (a or "").strip()
        if not q:
            continue
        if len(a) > MEMORY_ANSWER_CHARS:
            a = a[:MEMORY_ANSWER_CHARS].rsplit(" ", 1)[0] + "…"
        turns.append(Turn(q, a))
    return turns[-MEMORY_MAX_TURNS:]


def format_history(turns: List[Turn]) -> str:
    # Rótulos neutros: com "Usuário:/Assistente:" modelos pequenos passam a
    # narrar a conversa ("o assistente identificou…") em vez de responder.
    if not turns:
        return "(início da conversa)"
    return "\n".join(
        f"Pergunta anterior: {t.question}\nResposta anterior: {t.answer}" for t in turns
    )


# ---------------------------------------------------------------------------
# Detecção de perguntas de acompanhamento
# ---------------------------------------------------------------------------

# Conectivos que, no início, indicam continuação ("E a metodologia?").
_CONTINUATION = {"e", "mas", "entao", "tambem", "alem"}

# Pronomes e demonstrativos que retomam algo dito antes. ("esta" fica de fora:
# sem acento, confunde-se com o verbo "está".)
_ANAPHORA = {
    "ele", "ela", "eles", "elas", "dele", "dela", "deles", "delas",
    "nele", "nela", "neles", "nelas",
    "esse", "essa", "esses", "essas", "isso", "desse", "dessa", "desses",
    "dessas", "disso", "nesse", "nessa", "nesses", "nessas", "nisso",
    "este", "estes", "estas", "isto", "deste", "desta", "destes", "destas",
    "disto", "neste", "nesta", "nisto",
    "aquele", "aquela", "aquilo", "daquele", "daquela", "naquele", "naquela",
    "anterior", "mencionado", "mencionada", "citado", "citada",
}

# Termos genéricos de pesquisa: precedidos de artigo definido ("os dados",
# "a metodologia") costumam se referir ao estudo de que se falava.
_GENERIC = {
    "estudo", "pesquisa", "trabalho", "artigo", "autor", "autores", "autora",
    "experimento", "resultado", "resultados", "metodologia", "metodo",
    "conclusao", "conclusoes", "dados", "amostra", "participantes", "objetivo",
    "objetivos", "tratamento", "tratamentos", "delineamento", "limitacoes",
    "analise", "discussao", "referencias", "hipotese", "problema",
}
_DEFINITE = {"o", "a", "os", "as", "do", "da", "dos", "das", "no", "na", "nos", "nas"}

_GENERIC_STEMS = {stem(t) for t in _GENERIC}


def is_follow_up(question: str) -> bool:
    """Heurística: a pergunta depende da conversa anterior para fazer sentido?"""
    ws = words(question)
    if not ws:
        return False
    if ws[0] in _CONTINUATION:
        return True
    if any(w in _ANAPHORA for w in ws):
        return True
    if any(a in _DEFINITE and b in _GENERIC for a, b in zip(ws, ws[1:])):
        return True
    # Quase nenhum termo específico ("Quais as conclusões?", "Resuma melhor").
    return len(_specific_stems(question)) <= 1


def _specific_stems(text: str) -> set:
    return {stem(t) for t in tokenize(text)} - _GENERIC_STEMS


# ---------------------------------------------------------------------------
# Reescrita
# ---------------------------------------------------------------------------

_PREFIX = re.compile(r"^(pergunta\s+reescrita|pergunta|reescrita)\s*:\s*", re.IGNORECASE)


def _clean(raw: str) -> str:
    """Primeira linha útil da saída do modelo (ignora preâmbulos "Aqui está…:")."""
    for line in (raw or "").splitlines():
        line = _PREFIX.sub("", line.strip()).strip().strip('"“”*').strip()
        if line and not line.endswith(":"):
            return line
    return ""


class QuestionCondenser:
    """Resolve perguntas de acompanhamento com base no histórico."""

    def __init__(self, llm) -> None:
        self.chain = ChatPromptTemplate.from_template(CONDENSE_PROMPT) | llm | StrOutputParser()

    def resolve(self, question: str, turns: List[Turn]) -> Resolution:
        if not turns or not is_follow_up(question):
            return Resolution(standalone=question, queries=[question])

        expansion = f"{turns[-1].question} {question}"
        raw = self.chain.invoke({"history": format_history(turns), "question": question})
        rewrite = _clean(raw)

        # Aceita a reescrita só se ela trouxe algo específico do histórico.
        history_terms = _specific_stems(" ".join(f"{t.question} {t.answer}" for t in turns))
        brought = (_specific_stems(rewrite) & history_terms) - _specific_stems(question)
        if rewrite and len(rewrite) <= max(300, 3 * len(question)) and brought:
            return Resolution(standalone=rewrite, queries=[rewrite, expansion], mode="rewrite")
        return Resolution(standalone=expansion, queries=[expansion], mode="expansion")
