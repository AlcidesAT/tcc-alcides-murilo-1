/**
 * Painel "Coleta da pesquisa" (exclusivo do Administrador).
 *
 * Mostra os números principais dos testes com a turma (perguntas, tempo de
 * resposta, nota média, respostas precisas, fundamentação e questionário) e
 * guarda o restante em "Ver detalhes": sessões, distribuição das estrelas,
 * confiança automática, memória, resultado por modelo e cada critério do
 * questionário. Ali também ficam os botões que exportam cada conjunto em CSV
 * para a análise do TCC. Atualiza
 * ao entrar como admin e ao clicar em ↻.
 */

import * as api from "./api.js";
import { escapeHtml } from "./utils.js";

const keyEl = document.getElementById("eval-key");
const detailsEl = document.getElementById("eval-details-body");
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
    if (api.isAdmin()) loadAll();
}

async function loadAll() {
    keyEl.innerHTML = '<p class="empty">Carregando…</p>';
    detailsEl.innerHTML = "";
    const results = await Promise.allSettled([
        api.getCollectionSummary(),
        api.getEvaluationSummary(),
        api.getSurveySummary(),
    ]);
    const [c, r, s] = results.map((p) => (p.status === "fulfilled" ? p.value : null));
    const errors = results.filter((p) => p.status === "rejected").map((p) => p.reason?.message);

    if (!c && !r && !s) {
        keyEl.innerHTML = `<p class="empty">${escapeHtml(errors[0] || "Erro ao carregar.")}</p>`;
        return;
    }
    keyEl.innerHTML = renderKey(c, r, s);
    detailsEl.innerHTML =
        errors.map((m) => `<p class="empty">${escapeHtml(m)}</p>`).join("") + renderDetails(c, r, s);
}

/** Os seis números que respondem "como o sistema se saiu". */
function renderKey(c, r, s) {
    const rated = r?.total ? r : null;
    const answered = s?.respondentes ? s : null;
    return (
        `<div class="eval-tiles">` +
        tile(c ? String(c.perguntas) : "—", "perguntas", "", "Perguntas registradas") +
        tile(
            c?.tempo_medio_s == null ? "—" : `${num(c.tempo_medio_s)}<small> s</small>`,
            "tempo médio", "", "Da pergunta ao fim da resposta",
        ) +
        tile(
            rated ? `${num(rated.rating_avg)}<small>/5</small>` : "—",
            "nota média", rated ? `${rated.total} notas` : "sem notas", "Média das estrelas dadas às respostas",
        ) +
        tile(rated ? pct(rated.precise_rate) : "—", "precisas", "nota ≥ 4", "Respostas com nota 4 ou 5") +
        tile(
            rated ? pct(rated.groundedness_avg) : "—",
            "fundamentação", "automática", "Média da fundamentação automática nos trechos",
        ) +
        tile(
            answered ? `${num(answered.media_geral)}<small>/5</small>` : "—",
            "questionário", answered ? `${answered.respondentes} respondentes` : "sem respostas",
            "Média de todas as afirmações do questionário",
        ) +
        `</div>`
    );
}

/** O restante, aberto só quando o admin quer olhar a fundo. */
function renderDetails(c, r, s) {
    let html = "";
    if (c) {
        html +=
            `<div class="eval-subhead">Coleta</div>` +
            `<div class="eval-levels"><b>${c.sessoes}</b> sessões · <b>${c.perguntas_avaliadas}</b> perguntas com nota</div>`;
    }
    if (r?.total) {
        const lv = r.levels;
        const models = r.by_model
            .map(
                (m) =>
                    `<li><span class="eval-model" data-tip="${escapeHtml(m.model)}">${escapeHtml(m.model)}</span>` +
                    `<span>${m.total} · ${num(m.rating_avg)}★ · ${pct(m.groundedness_avg)}</span></li>`,
            )
            .join("");
        html +=
            `<div class="eval-subhead">Notas das respostas</div>` +
            `<div class="eval-bars">${bars(r.rating_distribution)}</div>` +
            `<div class="eval-levels">Confiança automática: ` +
            `<b>${lv.alta}</b> alta · <b>${lv.media}</b> média · <b>${lv.baixa}</b> baixa</div>` +
            (r.with_memory ? `<div class="eval-levels">${r.with_memory} com memória de conversa</div>` : "") +
            (models ? `<ul class="eval-models">${models}</ul>` : "");
    }
    if (s?.respondentes) {
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
        html += `<div class="eval-subhead">Questionário por critério</div><div class="survey-stats">${items}</div>`;
    }
    return html || '<p class="empty">Nada coletado ainda.</p>';
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

function tile(value, label, sub = "", tip = "") {
    const tipAttr = tip ? ` data-tip="${escapeHtml(tip)}"` : "";
    const subHtml = sub ? `<em>${escapeHtml(sub)}</em>` : "";
    return `<div class="eval-tile"${tipAttr}><strong>${value}</strong><span>${label}</span>${subHtml}</div>`;
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
