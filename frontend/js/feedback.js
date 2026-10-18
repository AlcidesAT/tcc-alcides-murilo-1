/**
 * Avaliação da precisão de cada resposta.
 *
 *  - Selo de confiança: mostra a fundamentação calculada automaticamente pelo
 *    backend (fração das frases da resposta apoiadas nos trechos recuperados).
 *  - Nota do usuário: 1 a 5 estrelas + comentário opcional, gravada no banco
 *    para a análise de precisão do TCC. Ao salvar, dispara o evento
 *    "evaluation:saved" (o painel do Administrador se atualiza).
 */

import * as api from "./api.js";

const LEVEL_LABELS = {
    alta: "Confiança alta",
    media: "Confiança média",
    baixa: "Confiança baixa",
    indefinido: "Confiança indefinida",
};

const RATING_LABELS = {
    1: "Totalmente imprecisa",
    2: "Pouco precisa",
    3: "Parcialmente precisa",
    4: "Precisa",
    5: "Totalmente precisa",
};

const pct = (v) => (v == null ? "—" : `${Math.round(v * 100)}%`);

export function buildQualityBadge(evaluation) {
    if (!evaluation) return null;
    const level = evaluation.level || "indefinido";

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
    el.textContent = `${LEVEL_LABELS[level] || level} · fundamentação ${pct(evaluation.groundedness)}`;
    el.setAttribute(
        "data-tip",
        `${evaluation.supported_sentences ?? 0} de ${evaluation.sentences ?? 0} frases da resposta ` +
            `estão apoiadas nos trechos recuperados. ` +
            `Cobertura da pergunta pelos trechos: ${pct(evaluation.question_coverage)}.`,
    );
    return el;
}

/**
 * Widget de nota. `interaction` traz o contexto da resposta avaliada:
 * { question, standalone_question, answer, scope, sources, used_memory, evaluation, model }.
 */
export function buildFeedback(interaction) {
    const box = document.createElement("div");
    box.className = "feedback";

    const label = document.createElement("span");
    label.className = "feedback-label";
    label.textContent = "Esta resposta foi precisa?";

    const stars = document.createElement("div");
    stars.className = "stars";
    stars.setAttribute("role", "radiogroup");
    stars.setAttribute("aria-label", "Nota de precisão de 1 a 5");

    const hint = document.createElement("span");
    hint.className = "feedback-hint";

    const extra = document.createElement("div");
    extra.className = "feedback-extra";
    extra.hidden = true;

    const comment = document.createElement("textarea");
    comment.rows = 2;
    comment.maxLength = 2000;
    comment.placeholder = "Comentário opcional: o que estava certo, errado ou faltando?";

    const send = document.createElement("button");
    send.type = "button";
    send.className = "feedback-send";
    send.textContent = "Enviar avaliação";

    const status = document.createElement("span");
    status.className = "feedback-status";

    extra.append(comment, send, status);

    let rating = 0;
    const buttons = [1, 2, 3, 4, 5].map((n) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "star";
        b.textContent = "★";
        b.title = `${n} — ${RATING_LABELS[n]}`;
        b.setAttribute("role", "radio");
        b.setAttribute("aria-checked", "false");
        b.setAttribute("aria-label", `${n} — ${RATING_LABELS[n]}`);
        b.addEventListener("click", () => select(n));
        b.addEventListener("mouseenter", () => paint(n));
        b.addEventListener("mouseleave", () => paint(rating));
        stars.appendChild(b);
        return b;
    });

    function paint(upTo) {
        buttons.forEach((b, i) => b.classList.toggle("on", i < upTo));
        hint.textContent = upTo ? RATING_LABELS[upTo] : "";
    }

    function select(n) {
        rating = n;
        buttons.forEach((b, i) => b.setAttribute("aria-checked", String(i + 1 === n)));
        paint(n);
        extra.hidden = false;
        status.textContent = "";
    }

    send.addEventListener("click", async () => {
        if (!rating) return;
        send.disabled = true;
        status.className = "feedback-status";
        status.textContent = "Enviando…";
        const ev = interaction.evaluation || {};
        try {
            await api.sendEvaluation({
                question: interaction.question,
                standalone_question: interaction.standalone_question,
                answer: interaction.answer,
                scope: interaction.scope,
                sources: interaction.sources || [],
                used_memory: Boolean(interaction.used_memory),
                rating,
                comment: comment.value.trim() || null,
                metrics: {
                    groundedness: ev.groundedness ?? null,
                    question_coverage: ev.question_coverage ?? null,
                    level: ev.level ?? null,
                },
                model: interaction.model || null,
            });
            box.classList.add("sent");
            box.innerHTML = "";
            const done = document.createElement("span");
            done.className = "feedback-done";
            done.textContent = `✓ Avaliação registrada (nota ${rating}/5). Obrigado!`;
            box.appendChild(done);
            document.dispatchEvent(new CustomEvent("evaluation:saved"));
        } catch (err) {
            status.className = "feedback-status error";
            status.textContent = `Não foi possível salvar: ${err.message}`;
            send.disabled = false;
        }
    });

    box.append(label, stars, hint, extra);
    return box;
}
