/**
 * Questionário de avaliação do sistema ("★ Avaliar o sistema").
 *
 * Só para o login da turma. As afirmações vêm do backend
 * (data/evaluation/questionario.json): cada uma recebe de 1 a 5 estrelas
 * (escala de concordância) e, no final, há um comentário livre. Cada sessão
 * responde uma vez; reabrir mostra o que foi enviado, e reenviar substitui.
 */

import * as api from "./api.js";
import { escapeHtml } from "./utils.js";
import { buildStarRating } from "./feedback.js";

const modal = document.getElementById("survey-modal");
const form = document.getElementById("survey-form");
const titleEl = document.getElementById("survey-title");
const bodyEl = document.getElementById("survey-body");
const statusEl = document.getElementById("survey-status");
const submitBtn = document.getElementById("survey-submit");
const openBtn = document.getElementById("survey-open");

let ratings = {}; // id da afirmação -> componente de estrelas
let commentEl = null;

export function initSurvey() {
    openBtn.addEventListener("click", openSurvey);
    document.getElementById("survey-close").addEventListener("click", close);
    document.getElementById("survey-cancel").addEventListener("click", close);
    modal.addEventListener("click", (e) => {
        if (e.target === modal) close();
    });
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && !modal.hidden) close();
    });
    form.addEventListener("submit", submit);
    document.addEventListener("rolechange", (e) => {
        if (!e.detail?.participant) close();
    });
}

async function openSurvey() {
    modal.hidden = false;
    submitBtn.hidden = false;
    submitBtn.disabled = true;
    setStatus("");
    bodyEl.innerHTML = '<p class="reader-msg">Carregando…</p>';
    try {
        render(await api.getSurvey());
        submitBtn.disabled = false;
    } catch (err) {
        bodyEl.innerHTML = `<p class="reader-msg error">${escapeHtml(err.message)}</p>`;
    }
}

function close() {
    modal.hidden = true;
}

function setStatus(text, kind = "") {
    statusEl.textContent = text;
    statusEl.className = `survey-status ${kind}`;
}

function render(survey) {
    titleEl.textContent = survey.titulo || "Avaliação do sistema";
    const previous = survey.resposta;
    ratings = {};
    bodyEl.innerHTML = "";

    const intro = document.createElement("p");
    intro.className = "survey-intro";
    intro.textContent = survey.introducao || "";
    bodyEl.appendChild(intro);

    if (previous) {
        const note = document.createElement("p");
        note.className = "survey-previous";
        note.textContent = "Você já enviou esta avaliação. Se mudar algo e enviar de novo, ela será substituída.";
        bodyEl.appendChild(note);
    }

    const list = document.createElement("ol");
    list.className = "survey-items";
    survey.afirmacoes.forEach((item) => {
        const li = document.createElement("li");
        li.className = "survey-item";
        li.dataset.id = item.id;

        const text = document.createElement("div");
        text.className = "survey-text";
        text.innerHTML =
            (item.criterio ? `<span class="survey-criterio">${escapeHtml(item.criterio)}</span>` : "") +
            `<span>${escapeHtml(item.texto)}</span>`;

        const stars = buildStarRating({
            labels: survey.escala,
            ariaLabel: item.texto,
            value: previous?.answers?.[item.id] || 0,
            onChange: () => li.classList.remove("missing"),
        });
        ratings[item.id] = stars;

        const rate = document.createElement("div");
        rate.className = "survey-rate";
        rate.append(stars.el, stars.hint);

        li.append(text, rate);
        list.appendChild(li);
    });
    bodyEl.appendChild(list);

    const label = document.createElement("label");
    label.className = "survey-comment-label";
    label.textContent = survey.comentario || "Comentário final";
    label.htmlFor = "survey-comment";
    commentEl = document.createElement("textarea");
    commentEl.id = "survey-comment";
    commentEl.rows = 4;
    commentEl.maxLength = 4000;
    commentEl.placeholder = "Escreva aqui (opcional)";
    commentEl.value = previous?.comment || "";
    bodyEl.append(label, commentEl);
}

async function submit(e) {
    e.preventDefault();
    const answers = {};
    const missing = [];
    Object.entries(ratings).forEach(([id, stars]) => {
        if (stars.value) answers[id] = stars.value;
        else missing.push(id);
    });

    bodyEl.querySelectorAll(".survey-item").forEach((li) =>
        li.classList.toggle("missing", missing.includes(li.dataset.id)),
    );
    if (missing.length) {
        setStatus(
            missing.length === 1
                ? "Falta avaliar 1 afirmação."
                : `Faltam ${missing.length} afirmações para avaliar.`,
            "error",
        );
        bodyEl.querySelector(".survey-item.missing")?.scrollIntoView({ block: "center", behavior: "smooth" });
        return;
    }

    submitBtn.disabled = true;
    setStatus("Enviando…");
    try {
        await api.sendSurvey(answers, commentEl.value.trim() || null);
        bodyEl.innerHTML =
            '<div class="survey-thanks"><div class="survey-thanks-mark">★</div>' +
            "<h4>Obrigado pela avaliação!</h4>" +
            "<p>Suas respostas foram registradas. Você pode continuar usando o sistema normalmente.</p></div>";
        submitBtn.hidden = true;
        setStatus("");
        document.dispatchEvent(new CustomEvent("evaluation:saved"));
    } catch (err) {
        setStatus(`Não foi possível enviar: ${err.message}`, "error");
        submitBtn.disabled = false;
    }
}
