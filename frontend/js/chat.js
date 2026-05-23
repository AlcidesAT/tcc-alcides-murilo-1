/**
 * Painel de chat (lado direito).
 *
 * Responsável por:
 *  - Manter o seletor de escopo: pasta + artigo (artigo só aparece se há >1)
 *  - Enviar a pergunta ao backend (com os filtros escolhidos)
 *  - Exibir mensagens, indicador de digitação, fontes recuperadas e a tag
 *    de escopo aplicada à resposta
 */

import * as api from "./api.js";
import { escapeHtml } from "./utils.js";

const scopeFolder = document.getElementById("scope-folder");
const scopeArticle = document.getElementById("scope-article");
const scopeArticleWrap = document.getElementById("scope-article-wrap");
const messagesEl = document.getElementById("messages");
const askForm = document.getElementById("ask-form");
const questionEl = document.getElementById("question");
const askBtn = document.getElementById("ask-btn");

let documentsByFolder = {};

export function initChat() {
    scopeFolder.addEventListener("change", () => updateArticleOptions(""));
    askForm.addEventListener("submit", handleSubmit);
    questionEl.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            askForm.requestSubmit();
        }
    });
}

export function updateScopeSelectors({ folders, documentsByFolder: dbf }) {
    documentsByFolder = dbf;

    const prevFolder = scopeFolder.value;
    const prevArticle = scopeArticle.value;

    scopeFolder.innerHTML = '<option value="">Todas as pastas</option>';
    folders.forEach((f) => {
        const opt = document.createElement("option");
        opt.value = f.folder;
        opt.textContent = `${f.folder} (${f.documents} doc.)`;
        scopeFolder.appendChild(opt);
    });
    scopeFolder.value = folders.some((f) => f.folder === prevFolder)
        ? prevFolder
        : "";

    updateArticleOptions(prevArticle);
}

function updateArticleOptions(preferred = "") {
    const folder = scopeFolder.value;
    const docs = folder ? documentsByFolder[folder] || [] : [];

    scopeArticle.innerHTML = '<option value="">Todos os artigos</option>';
    docs.forEach((d) => {
        const opt = document.createElement("option");
        opt.value = d.source;
        opt.textContent = d.source;
        scopeArticle.appendChild(opt);
    });

    if (folder && docs.length > 1) {
        scopeArticleWrap.hidden = false;
        scopeArticle.value = docs.some((d) => d.source === preferred)
            ? preferred
            : "";
    } else {
        scopeArticleWrap.hidden = true;
        scopeArticle.value = "";
    }
}

async function handleSubmit(e) {
    e.preventDefault();
    const q = questionEl.value.trim();
    if (!q) return;

    const folder = scopeFolder.value || null;
    const source =
        folder && !scopeArticleWrap.hidden && scopeArticle.value
            ? scopeArticle.value
            : null;

    appendMessage("user", q);
    questionEl.value = "";
    askBtn.disabled = true;
    const typing = appendTyping();

    try {
        const data = await api.ask(q, folder, source);
        typing.remove();
        appendMessage("bot", data.answer, data.sources, data.scope);
    } catch (err) {
        typing.remove();
        appendMessage("bot", `Erro: ${err.message}`);
    } finally {
        askBtn.disabled = false;
        questionEl.focus();
    }
}

function appendMessage(role, text, sources, scope) {
    const wrap = document.createElement("div");
    wrap.className = `msg ${role}`;
    const bubble = document.createElement("div");
    bubble.className = "bubble";

    if (scope && role === "bot") {
        const tag = document.createElement("div");
        tag.className = "scope-tag";
        if (scope === "todas") {
            tag.textContent = "Escopo: todas as pastas";
        } else if (scope.includes(" / ")) {
            const [f, a] = scope.split(" / ");
            tag.textContent = `Escopo: pasta "${f}" · artigo "${a}"`;
        } else {
            tag.textContent = `Escopo: pasta "${scope}"`;
        }
        bubble.appendChild(tag);
    }

    const body = document.createElement("div");
    body.textContent = text;
    bubble.appendChild(body);

    if (sources && sources.length) {
        const sBox = document.createElement("div");
        sBox.className = "sources";
        sBox.innerHTML =
            "<strong>Fontes utilizadas:</strong><ul>" +
            sources
                .map(
                    (s) =>
                        `<li><b>${escapeHtml(s.folder)} / ${escapeHtml(
                            s.source
                        )}</b> (p. ${escapeHtml(String(s.page))}): ${escapeHtml(
                            s.snippet
                        )}</li>`
                )
                .join("") +
            "</ul>";
        bubble.appendChild(sBox);
    }

    wrap.appendChild(bubble);
    messagesEl.appendChild(wrap);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return bubble;
}

function appendTyping() {
    const wrap = document.createElement("div");
    wrap.className = "msg bot";
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.innerHTML =
        '<div class="typing"><span></span><span></span><span></span></div>';
    wrap.appendChild(bubble);
    messagesEl.appendChild(wrap);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return wrap;
}
