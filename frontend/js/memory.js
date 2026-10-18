/**
 * Memória de pergunta (memória da conversa).
 *
 * Guarda os pares pergunta/resposta da conversa atual e os envia ao backend a
 * cada nova pergunta. Assim, perguntas de acompanhamento ("e qual foi a
 * metodologia dele?") são reescritas no contexto da conversa antes da busca.
 *
 * A faixa acima do campo de pergunta mostra quantas perguntas anteriores serão
 * consideradas e permite "Esquecer" (limpar a memória sem apagar as mensagens).
 * "Nova conversa" também limpa a memória.
 */

// Quantos pares enviamos; o backend usa só os `maxTurns` mais recentes.
const SEND_LIMIT = 10;

const bar = document.getElementById("memory-bar");
const barText = document.getElementById("memory-text");
const clearBtn = document.getElementById("memory-clear");

let turns = [];
let maxTurns = 4; // atualizado com o valor do backend (memory_max_turns)
// Muda a cada limpeza; uma resposta que termina depois de "Nova conversa"
// ou "Esquecer" não entra na memória nova.
let epoch = 0;

export function initMemory({ onForget } = {}) {
    clearBtn.addEventListener("click", () => {
        clearMemory();
        onForget?.();
    });
    render();
}

export function getHistory() {
    return turns.slice(-SEND_LIMIT);
}

export function memoryEpoch() {
    return epoch;
}

export function remember(question, answer, askedAt = epoch) {
    if (askedAt !== epoch) return;
    turns.push({ question, answer });
    render();
}

export function setMaxTurns(n) {
    if (Number.isInteger(n) && n > 0) maxTurns = n;
    render();
}

export function clearMemory() {
    turns = [];
    epoch += 1;
    render();
}

function render() {
    const n = Math.min(turns.length, maxTurns);
    bar.hidden = n === 0;
    barText.textContent =
        n === 1
            ? "Memória ativa: a próxima pergunta considera a pergunta anterior."
            : `Memória ativa: a próxima pergunta considera as ${n} últimas perguntas.`;
}
