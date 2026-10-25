/**
 * Painel "Coleta da pesquisa" (exclusivo do Administrador).
 *
 * Mostra o que foi registrado com o login da turma: totais da coleta
 * (sessões, perguntas, tempo de resposta), as notas dadas às respostas
 * (com a fundamentação automática) e o resultado do questionário de avaliação
 * do sistema. Exporta cada conjunto em CSV para a análise do TCC. Atualiza ao
 * entrar como admin, ao clicar em ↻ e sempre que uma avaliação é registrada.
 */

import * as api from "./api.js";
import { escapeHtml } from "./utils.js";

const collectionEl = document.getElementById("collection-summary");
const summaryEl = document.getElementById("eval-summary");
const surveyEl = document.getElementById("survey-summary");
const refreshBtn = document.getElementById("eval-refresh");

const pct = (v) => (v == null ? "—" : `${Math.round(v * 100)}%`);
const num = (v) => (v == null ? "—" : v.toFixed(1).replace(".", ","));

export function initEvaluation() {
    refreshBtn.addEventListener("click", loadAll);
    document.querySelectorAll(".export-btn").forEach((btn) =>
        btn.addEventListener("click", () => exportCsv(btn)),
    );
    document.addEventListener("rolechange", (e) => {
        if (e.detail?.admin) loadAll();
    });
    document.addEventListener("evaluation:saved", () => {
        if (api.isAdmin()) loadAll();
    });
    if (api.isAdmin()) loadAll();
}

function loadAll() {
    load(collectionEl, api.getCollectionSummary, renderCollection);
    load(summaryEl, api.getEvaluationSummary, renderRatings);
    load(surveyEl, api.getSurveySummary, renderSurvey);
}

async function load(el, fetcher, render) {
    el.innerHTML = '<p class="empty">Carregando…</p>';
    try {
        el.innerHTML = render(await fetcher());
    } catch (err) {
        el.innerHTML = `<p class="empty">${escapeHtml(err.message)}</p>`;
    }
}

function renderCollection(c) {
    return (
        `<div class="eval-tiles">` +
        tile(String(c.sessoes), "sessões", "Entradas com o login da turma") +
        tile(String(c.perguntas), "perguntas", "Perguntas registradas") +
        tile(String(c.perguntas_avaliadas), "com nota", "Perguntas que receberam estrelas") +
        tile(c.tempo_medio_s == null ? "—" : `${num(c.tempo_medio_s)}<small> s</small>`, "tempo médio", "Da pergunta ao fim da resposta") +
        `</div>`
    );
}

function bars(distribution) {
    const maxCount = Math.max(1, ...Object.values(distribution));
    return [5, 4, 3, 2, 1]
        .map((n) => {
            const c = distribution[String(n)] || 0;
            return (
                `<div class="eval-bar"><span>${n}★</span>` +
                `<div class="eval-bar-track"><div class="eval-bar-fill" style="width:${(c / maxCount) * 100}%"></div></div>` +
                `<span>${c}</span></div>`
            );
        })
        .join("");
}

function renderRatings(s) {
    if (!s.total) {
        return '<p class="empty">Nenhuma nota ainda. As estrelas dadas às respostas aparecerão aqui.</p>';
    }
    const lv = s.levels;
    const models = s.by_model
        .map(
            (m) =>
                `<li><span class="eval-model" data-tip="${escapeHtml(m.model)}">${escapeHtml(m.model)}</span>` +
                `<span>${m.total} · ${num(m.rating_avg)}★ · ${pct(m.groundedness_avg)}</span></li>`,
        )
        .join("");

    return (
        `<div class="eval-tiles">` +
        tile(String(s.total), "notas") +
        tile(`${num(s.rating_avg)}<small>/5</small>`, "nota média") +
        tile(pct(s.precise_rate), "precisas (nota ≥ 4)", "Respostas com nota 4 ou 5") +
        tile(pct(s.groundedness_avg), "fundamentação", "Média da fundamentação automática nos trechos") +
        `</div>` +
        `<div class="eval-bars">${bars(s.rating_distribution)}</div>` +
        `<div class="eval-levels">Confiança automática: ` +
        `<b>${lv.alta}</b> alta · <b>${lv.media}</b> média · <b>${lv.baixa}</b> baixa</div>` +
        (s.with_memory ? `<div class="eval-levels">${s.with_memory} com memória de conversa</div>` : "") +
        (models ? `<ul class="eval-models">${models}</ul>` : "")
    );
}

function renderSurvey(s) {
    if (!s.respondentes) {
        return '<p class="empty">Nenhum questionário respondido ainda.</p>';
    }
    const items = s.afirmacoes
        .map((a) => {
            const width = a.media == null ? 0 : (a.media / 5) * 100;
            return (
                `<div class="survey-stat" data-tip="${escapeHtml(a.texto)}">` +
                `<span class="survey-stat-name">${escapeHtml(a.criterio)}</span>` +
                `<div class="eval-bar-track"><div class="eval-bar-fill" style="width:${width}%"></div></div>` +
                `<span class="survey-stat-avg">${num(a.media)}</span></div>`
            );
        })
        .join("");
    return (
        `<div class="eval-tiles">` +
        tile(String(s.respondentes), "respondentes") +
        tile(`${num(s.media_geral)}<small>/5</small>`, "média geral", "Média de todas as afirmações") +
        `</div>` +
        `<div class="survey-stats">${items}</div>`
    );
}

function tile(value, label, tip = "") {
    const tipAttr = tip ? ` data-tip="${escapeHtml(tip)}"` : "";
    return `<div class="eval-tile"${tipAttr}><strong>${value}</strong><span>${label}</span></div>`;
}

async function exportCsv(btn) {
    btn.disabled = true;
    try {
        await api.downloadCsv(btn.dataset.path, btn.dataset.file);
    } catch (err) {
        alert(err.message);
    } finally {
        btn.disabled = false;
    }
}
