/**
 * Painel "Avaliação das respostas" (exclusivo do Administrador).
 *
 * Mostra os indicadores agregados das notas dados pelos usuários e das
 * métricas automáticas (fundamentação), e permite exportar tudo em CSV para
 * a análise de precisão do TCC. Atualiza ao entrar como admin, ao clicar em
 * ↻ e sempre que uma nova avaliação é registrada.
 */

import * as api from "./api.js";
import { escapeHtml } from "./utils.js";

const summaryEl = document.getElementById("eval-summary");
const refreshBtn = document.getElementById("eval-refresh");
const exportBtn = document.getElementById("eval-export");

const pct = (v) => (v == null ? "—" : `${Math.round(v * 100)}%`);
const num = (v) => (v == null ? "—" : v.toFixed(1).replace(".", ","));

export function initEvaluation() {
    refreshBtn.addEventListener("click", loadSummary);
    exportBtn.addEventListener("click", exportCsv);
    document.addEventListener("rolechange", (e) => {
        if (e.detail?.admin) loadSummary();
    });
    document.addEventListener("evaluation:saved", () => {
        if (api.isAdmin()) loadSummary();
    });
    if (api.isAdmin()) loadSummary();
}

async function loadSummary() {
    summaryEl.innerHTML = '<p class="empty">Carregando…</p>';
    try {
        render(await api.getEvaluationSummary());
    } catch (err) {
        summaryEl.innerHTML = `<p class="empty">${escapeHtml(err.message)}</p>`;
    }
}

function render(s) {
    if (!s.total) {
        summaryEl.innerHTML =
            '<p class="empty">Nenhuma avaliação ainda. As notas dadas às respostas aparecerão aqui.</p>';
        exportBtn.disabled = true;
        return;
    }
    exportBtn.disabled = false;

    const maxCount = Math.max(1, ...Object.values(s.rating_distribution));
    const bars = [5, 4, 3, 2, 1]
        .map((n) => {
            const c = s.rating_distribution[String(n)] || 0;
            return (
                `<div class="eval-bar"><span>${n}★</span>` +
                `<div class="eval-bar-track"><div class="eval-bar-fill" style="width:${(c / maxCount) * 100}%"></div></div>` +
                `<span>${c}</span></div>`
            );
        })
        .join("");

    const lv = s.levels;
    const models = s.by_model
        .map(
            (m) =>
                `<li><span class="eval-model" data-tip="${escapeHtml(m.model)}">${escapeHtml(m.model)}</span>` +
                `<span>${m.total} · ${num(m.rating_avg)}★ · ${pct(m.groundedness_avg)}</span></li>`,
        )
        .join("");

    summaryEl.innerHTML =
        `<div class="eval-tiles">` +
        tile(String(s.total), "avaliações") +
        tile(`${num(s.rating_avg)}<small>/5</small>`, "nota média") +
        tile(pct(s.precise_rate), "precisas (nota ≥ 4)", "Respostas com nota 4 ou 5") +
        tile(pct(s.groundedness_avg), "fundamentação", "Média da fundamentação automática nos trechos") +
        `</div>` +
        `<div class="eval-bars">${bars}</div>` +
        `<div class="eval-levels">Confiança automática: ` +
        `<b>${lv.alta}</b> alta · <b>${lv.media}</b> média · <b>${lv.baixa}</b> baixa</div>` +
        (s.with_memory ? `<div class="eval-levels">${s.with_memory} com memória de conversa</div>` : "") +
        (models ? `<ul class="eval-models">${models}</ul>` : "");
}

function tile(value, label, tip = "") {
    const tipAttr = tip ? ` data-tip="${escapeHtml(tip)}"` : "";
    return `<div class="eval-tile"${tipAttr}><strong>${value}</strong><span>${label}</span></div>`;
}

async function exportCsv() {
    exportBtn.disabled = true;
    try {
        await api.downloadEvaluationsCsv();
    } catch (err) {
        alert(err.message);
    } finally {
        exportBtn.disabled = false;
    }
}
