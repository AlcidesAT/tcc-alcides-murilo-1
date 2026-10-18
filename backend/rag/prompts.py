"""
Prompts do módulo de geração.
"""

ANSWER_PROMPT = """Você é um assistente especializado em responder perguntas sobre artigos científicos.
Baseie-se nos trechos fornecidos abaixo para responder à pergunta do usuário.
Você pode sintetizar, relacionar e interpretar as informações dos trechos para
elaborar uma resposta completa e bem estruturada — sem inventar dados que não
estejam apoiados no contexto. Se os trechos trouxerem apenas informação parcial,
responda com o que for possível e indique o que ficou em aberto. Só diga que não
há informação suficiente quando os trechos realmente não tiverem nenhuma relação
com a pergunta.
Responda em português do Brasil, de forma clara, objetiva e fundamentada,
citando, quando útil, os trechos/artigos que embasam a resposta.

{extra}Contexto recuperado dos artigos:
{context}

Pergunta: {question}

Resposta:"""

# Bloco inserido em {extra} só em perguntas de acompanhamento. Uma pergunta
# comum recebe o prompt acima sem ele (o mesmo da primeira entrega): modelos
# pequenos ecoam rótulos como "pergunta atual" e tentam ligar perguntas
# independentes à conversa anterior.
HISTORY_BLOCK = """Conversa anterior (serve só para entender a que a pergunta se refere; os
fatos da resposta devem vir dos trechos; não comente a conversa, apenas responda):
{history}

"""


# Memória de pergunta: transforma uma pergunta de acompanhamento ("e qual foi a
# metodologia dele?") em uma pergunta completa, que possa ser usada na busca.
CONDENSE_PROMPT = """Você reescreve perguntas de acompanhamento em uma conversa sobre artigos científicos.
Dado o histórico da conversa e a nova pergunta, reescreva a nova pergunta para
que ela seja compreensível sozinha, substituindo pronomes e referências vagas
("ele", "esse estudo", "e a metodologia?") pelos termos citados no histórico.
Se a nova pergunta já for completa ou mudar de assunto, devolva-a sem alterações.
NÃO responda à pergunta. Devolva apenas a pergunta reescrita, em uma única linha,
em português do Brasil.

Histórico da conversa:
{history}

Nova pergunta: {question}

Pergunta reescrita:"""
