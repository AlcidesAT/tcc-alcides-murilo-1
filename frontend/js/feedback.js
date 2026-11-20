/**
 * Selo de confiança de cada resposta: mostra a fundamentação calculada
 * automaticamente pelo backend (fração das frases da resposta apoiadas nos
 * trechos recuperados).
 */

const LEVEL_LABELS = {
    alta: "Confiança alta",
    media: "Confiança média",
    baixa: "Confiança baixa",
    indefinido: "Confiança indefinida",
};

const pct = (v) => (v == null ? "—" : `${Math.round(v * 100)}%`);

export function buildQualityBadge(evaluation) {
    if (!evaluation) return null;
    const level = evaluation.level || "indefinido";
    if (level === "conversa") return null; // cumprimento: não é resposta sobre os artigos

    const el = document.createElement("div");
    el.className = `quality-badge level-${level}`;
    if (level === "acervo") {
        el.textContent = "Lista do acervo";
        el.setAttribute(
            "data-tip",
            "Resposta montada diretamente do índice de artigos (títulos, assuntos e " +
                "conteúdo), sem o modelo de linguagem.",
        );
        return el;
    }
    if (level === "fora") {
        el.textContent = "Fora dos artigos";
        el.setAttribute(
            "data-tip",
            "Nada no acervo trata desta pergunta.",
        );
        return el;
    }
    el.textContent = `${LEVEL_LABELS[level] || level} · fundamentação ${pct(evaluation.groundedness)}`;
    el.setAttribute(
        "data-tip",
        `${evaluation.supported_sentences ?? 0} de ${evaluation.sentences ?? 0} frases da resposta ` +
            `estão apoiadas nos trechos recuperados. ` +
            `Cobertura da pergunta pelos trechos: ${pct(evaluation.question_coverage)}.`,
    );
    return el;
}
