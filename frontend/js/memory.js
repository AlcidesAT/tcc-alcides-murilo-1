/**
 * Memória de pergunta (memória da conversa).
 *
 * Funciona em segundo plano, sem opção para o usuário: guarda os pares
 * pergunta/resposta da conversa atual e os envia ao backend a cada nova
 * pergunta. Assim, perguntas de acompanhamento ("e qual foi a metodologia
 * dele?") são reescritas no contexto da conversa antes da busca.
 * "Nova conversa" limpa a memória.
 */

// Quantos pares enviamos; o backend usa só os mais recentes (MEMORY_MAX_TURNS).
const SEND_LIMIT = 10;

let turns = [];
// Muda a cada limpeza; uma resposta que termina depois de "Nova conversa"
// não entra na memória nova.
let epoch = 0;

export function getHistory() {
    return turns.slice(-SEND_LIMIT);
}

export function memoryEpoch() {
    return epoch;
}

export function remember(question, answer, askedAt = epoch) {
    if (askedAt !== epoch) return;
    turns.push({ question, answer });
}

export function clearMemory() {
    turns = [];
    epoch += 1;
}
