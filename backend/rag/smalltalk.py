"""
Cumprimentos e agradecimentos ("oi", "bom dia", "obrigado", "tchau").

Não são perguntas sobre os artigos, mas passam pelo filtro de assunto: "oi"
aparece em algum trecho do acervo, então a busca trazia trechos quaisquer e o
modelo inventava uma resposta sobre eles. Agora a mensagem feita só de palavras
de conversa recebe uma resposta pronta, sem busca e sem o LLM.
"""

from typing import Optional

from rag.lexical import words

_GREETING = {
    "oi", "oie", "oii", "oiii", "ola", "ei", "opa", "eai", "eae", "salve", "hey",
    "hello", "hi", "alo", "saudacoes", "bom", "boa", "dia", "tarde", "noite",
    "tudo", "bem", "td", "beleza", "blz", "tranquilo", "tranquila", "suave",
    "como", "vai", "vc", "voce", "esta", "ta", "e", "ai", "com", "pessoal", "assistente",
}
_THANKS = {
    "obrigado", "obrigada", "obg", "brigado", "brigada", "valeu", "vlw", "agradeco",
    "grato", "grata", "thanks", "muito", "mto", "muitissimo", "pela", "ajuda",
}
_ACK = {"ok", "okay", "certo", "entendi", "legal", "show", "otimo", "otima", "perfeito", "massa", "beleza", "blz"}
_FAREWELL = {"tchau", "ate", "logo", "mais", "breve", "adeus", "falou", "flw", "bye"}

# Palavras que sozinhas não fazem uma saudação ("e", "como", "muito"...): a
# mensagem precisa ter pelo menos uma destas.
_GREETING_CORE = {
    "oi", "oie", "oii", "oiii", "ola", "ei", "opa", "eai", "eae", "salve", "hey",
    "hello", "hi", "alo", "saudacoes", "bom", "boa", "tudo", "td", "vai",
}
_THANKS_CORE = {
    "obrigado", "obrigada", "obg", "brigado", "brigada", "valeu", "vlw", "agradeco",
    "grato", "grata", "thanks",
}
_FAREWELL_CORE = {"tchau", "adeus", "falou", "flw", "bye"}

# Mensagens maiores que isso são tratadas como pergunta.
_MAX_WORDS = 6

GREETING_ANSWER = (
    "Olá! Eu respondo perguntas sobre os artigos científicos do acervo. Escreva "
    "o que você quer saber, por exemplo sobre um tema, um método ou um resultado. "
    "Em “Como perguntar”, logo abaixo, estão os temas disponíveis e alguns modelos "
    "de pergunta."
)
THANKS_ANSWER = "De nada! Se quiser, faça outra pergunta sobre os artigos do acervo."
ACK_ANSWER = "Certo! Quando quiser, faça outra pergunta sobre os artigos do acervo."
FAREWELL_ANSWER = "Até mais! Quando quiser, é só voltar e perguntar sobre os artigos."


def small_talk_answer(message: str) -> Optional[str]:
    """Resposta pronta se a mensagem for só cumprimento/agradecimento; senão None."""
    ws = words(message)
    if not ws or len(ws) > _MAX_WORDS:
        return None
    vocabulary = _GREETING | _THANKS | _ACK | _FAREWELL
    if any(w not in vocabulary for w in ws):
        return None
    present = set(ws)
    if present & _THANKS_CORE:
        return THANKS_ANSWER
    if present & _FAREWELL_CORE or ("ate" in present and present & {"logo", "mais", "breve"}):
        return FAREWELL_ANSWER
    if present & _GREETING_CORE or ("e", "ai") in zip(ws, ws[1:]):
        return GREETING_ANSWER
    if present & _ACK:
        return ACK_ANSWER
    return None
