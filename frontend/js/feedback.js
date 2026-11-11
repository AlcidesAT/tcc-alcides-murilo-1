/**
 * Avaliação da precisão de cada resposta.
 *
 *  - Selo de confiança: mostra a fundamentação calculada automaticamente pelo
 *    backend (fração das frases da resposta apoiadas nos trechos recuperados).
 *  - Nota do participante (login da turma): 1 a 5 estrelas + comentário
 *    opcional, gravada no banco junto da pergunta registrada. Ao salvar,
 *    dispara o evento "evaluation:saved" (o painel do Administrador se atualiza).
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
    if (level === "fora") {
        el.textContent = "Fora dos artigos";
        el.setAttribute(
            "data-tip",
            "Nada no acervo trata desta pergunta. Ela não conta no limite nem é registrada.",
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
 * Estrelas de 1 a 5 (usadas na nota de cada resposta e no questionário).
 * `labels` traz o texto de cada nota; `onChange(n)` é chamado ao clicar.
 * Devolve { el, hint, get value, set(n) }.
 */
export function buildStarRating({ labels, ariaLabel, onChange, value = 0 }) {
    const el = document.createElement("div");
    el.className = "stars";
    el.setAttribute("role", "radiogroup");
    el.setAttribute("aria-label", ariaLabel);

    const hint = document.createElement("span");
    hint.className = "feedback-hint";

    let current = 0;
    const buttons = [1, 2, 3, 4, 5].map((n) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "star";
        b.textContent = "★";
        b.title = `${n} — ${labels[n]}`;
        b.setAttribute("role", "radio");
        b.setAttribute("aria-checked", "false");
        b.setAttribute("aria-label", `${n} — ${labels[n]}`);
        b.addEventListener("click", () => {
            set(n);
            onChange?.(n);
        });
        b.addEventListener("mouseenter", () => paint(n));
        b.addEventListener("mouseleave", () => paint(current));
        el.appendChild(b);
        return b;
    });

    function paint(upTo) {
        buttons.forEach((b, i) => b.classList.toggle("on", i < upTo));
        hint.textContent = upTo ? labels[upTo] : "";
    }

    function set(n) {
        current = n;
        buttons.forEach((b, i) => b.setAttribute("aria-checked", String(i + 1 === n)));
        paint(n);
    }

    if (value) set(value);
    return {
        el,
        hint,
        set,
        get value() {
            return current;
        },
    };
}

/**
 * Nota de precisão de uma resposta (só com o login da turma). `interaction`
 * traz o contexto da resposta avaliada: { interaction_id, question,
 * standalone_question, answer, scope, sources, used_memory, evaluation, model }.
 * Sem login de participante, devolve null (nada é registrado).
 */
export function buildFeedback(interaction) {
    if (!api.isParticipant()) return null;

    const box = document.createElement("div");
    box.className = "feedback";

    const label = document.createElement("span");
    label.className = "feedback-label";
    label.textContent = "Esta resposta foi precisa?";

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

    // Posts run one at a time, so fast clicks on different stars reach the
    // server in order and the last star clicked is the rating that stays.
    let pending = Promise.resolve();

    function post(rating, text) {
        const ev = interaction.evaluation || {};
        const request = pending.then(() =>
            api.sendEvaluation({
                interaction_id: interaction.interaction_id || null,
                question: interaction.question,
                standalone_question: interaction.standalone_question,
                answer: interaction.answer,
                scope: interaction.scope,
                sources: interaction.sources || [],
                used_memory: Boolean(interaction.used_memory),
                rating,
                comment: text,
                metrics: {
                    groundedness: ev.groundedness ?? null,
                    question_coverage: ev.question_coverage ?? null,
                    level: ev.level ?? null,
                },
                model: interaction.model || null,
            }),
        );
        pending = request.catch(() => {});
        return request;
    }

    const stars = buildStarRating({
        labels: RATING_LABELS,
        ariaLabel: "Nota de precisão de 1 a 5",
        onChange: (rating) => {
            extra.hidden = false;
            status.textContent = "";
            // The star click already saves the rating, silently: participants
            // picked a star, saw it lit and left without pressing "Enviar
            // avaliação", and nothing reached the database. The button still
            // works as before and replaces this row (same interaction_id).
            // Without interaction_id every POST inserts a new row, so only the
            // button saves there, as it always did.
            if (!interaction.interaction_id) return;
            post(rating, comment.value.trim() || null).then(
                () => document.dispatchEvent(new CustomEvent("evaluation:saved")),
                (err) => {
                    status.className = "feedback-status error";
                    status.textContent = `Não foi possível salvar: ${err.message}`;
                },
            );
        },
    });

    send.addEventListener("click", async () => {
        const rating = stars.value;
        if (!rating) return;
        send.disabled = true;
        status.className = "feedback-status";
        status.textContent = "Enviando…";
        try {
            await post(rating, comment.value.trim() || null);
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

    box.append(label, stars.el, stars.hint, extra);
    return box;
}
