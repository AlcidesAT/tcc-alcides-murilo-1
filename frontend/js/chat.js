/**
 * Painel de conversa (estilo ChatGPT).
 *
 * Responsável por:
 *  - Seletor de escopo: assunto + artigo (artigo só aparece se há >1)
 *  - Enviar a pergunta ao backend (com os filtros escolhidos)
 *  - Renderizar mensagens em linhas (usuário à direita em balão, assistente
 *    à esquerda com avatar e texto pleno), indicador de digitação e fontes
 *  - Estado inicial (hero), "Nova conversa" e recolher/abrir a sidebar
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
const emptyState = document.getElementById("empty-state");
const newChatBtn = document.getElementById("new-chat-btn");
const collapseBtn = document.getElementById("collapse-btn");
const openSidebarBtn = document.getElementById("open-sidebar-btn");
const appEl = document.getElementById("app");

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
    questionEl.addEventListener("input", autoResize);

    newChatBtn.addEventListener("click", newConversation);

    collapseBtn.addEventListener("click", () => appEl.classList.add("sidebar-hidden"));
    openSidebarBtn.addEventListener("click", () => appEl.classList.remove("sidebar-hidden"));

    document.querySelectorAll(".suggestion").forEach((btn) => {
        btn.addEventListener("click", () => {
            questionEl.value = btn.textContent;
            autoResize();
            questionEl.focus();
        });
    });
}

function autoResize() {
    questionEl.style.height = "auto";
    questionEl.style.height = Math.min(questionEl.scrollHeight, 200) + "px";
}

function newConversation() {
    messagesEl.innerHTML = "";
    emptyState.hidden = false;
    questionEl.value = "";
    autoResize();
    questionEl.focus();
}

export function updateScopeSelectors({ folders, documentsByFolder: dbf }) {
    documentsByFolder = dbf;

    const prevFolder = scopeFolder.value;
    const prevArticle = scopeArticle.value;

    scopeFolder.innerHTML = '<option value="">Todos os assuntos</option>';
    folders.forEach((f) => {
        const opt = document.createElement("option");
        opt.value = f.folder;
        opt.textContent = `${f.folder} (${f.documents} art.)`;
        scopeFolder.appendChild(opt);
    });
    scopeFolder.value = folders.some((f) => f.folder === prevFolder) ? prevFolder : "";

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
        scopeArticle.value = docs.some((d) => d.source === preferred) ? preferred : "";
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
        folder && !scopeArticleWrap.hidden && scopeArticle.value ? scopeArticle.value : null;

    emptyState.hidden = true;
    appendUser(q);
    questionEl.value = "";
    autoResize();
    askBtn.disabled = true;
    const typing = appendTyping();

    try {
        const data = await api.ask(q, folder, source);
        typing.remove();
        appendBot(data.answer, data.sources, data.scope);
    } catch (err) {
        typing.remove();
        appendBot(`Erro: ${err.message}`);
    } finally {
        askBtn.disabled = false;
        questionEl.focus();
    }
}

function appendUser(text) {
    const row = document.createElement("div");
    row.className = "msg-row user";
    const bubble = document.createElement("div");
    bubble.className = "msg-bubble";
    bubble.textContent = text;
    row.appendChild(bubble);
    messagesEl.appendChild(row);
    scrollToBottom();
}

function appendBot(text, sources, scope) {
    const row = document.createElement("div");
    row.className = "msg-row assistant";

    const avatar = document.createElement("div");
    avatar.className = "msg-avatar";
    avatar.textContent = "◆";

    const content = document.createElement("div");
    content.className = "msg-content";

    if (scope) {
        const tag = document.createElement("div");
        tag.className = "scope-tag";
        if (scope === "todas") {
            tag.textContent = "Todos os assuntos";
        } else if (scope.includes(" / ")) {
            const [f, a] = scope.split(" / ");
            tag.textContent = `Assunto: ${f} · Artigo: ${a}`;
        } else {
            tag.textContent = `Assunto: ${scope}`;
        }
        content.appendChild(tag);
    }

    const body = document.createElement("div");
    body.className = "msg-text";
    body.textContent = text;
    content.appendChild(body);

    if (sources && sources.length) {
        const sBox = document.createElement("div");
        sBox.className = "sources";
        sBox.innerHTML =
            "<strong>Fontes utilizadas:</strong><ul>" +
            sources
                .map(
                    (s) =>
                        `<li><b>${escapeHtml(s.folder)} / ${escapeHtml(s.source)}</b> ` +
                        `(p. ${escapeHtml(String(s.page))}): ${escapeHtml(s.snippet)}</li>`
                )
                .join("") +
            "</ul>";
        content.appendChild(sBox);
    }

    row.append(avatar, content);
    messagesEl.appendChild(row);
    scrollToBottom();
}

function appendTyping() {
    const row = document.createElement("div");
    row.className = "msg-row assistant";
    row.innerHTML =
        '<div class="msg-avatar">◆</div>' +
        '<div class="msg-content"><div class="typing"><span></span><span></span><span></span></div></div>';
    messagesEl.appendChild(row);
    scrollToBottom();
    return row;
}

function scrollToBottom() {
    const scroll = document.getElementById("chat-scroll");
    scroll.scrollTop = scroll.scrollHeight;
}
