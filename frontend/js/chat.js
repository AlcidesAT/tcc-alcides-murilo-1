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
import { escapeHtml, renderMarkdown } from "./utils.js";

const scopeFolder = document.getElementById("scope-folder");
const scopeArticle = document.getElementById("scope-article");
const scopeArticleWrap = document.getElementById("scope-article-wrap");
const messagesEl = document.getElementById("messages");
const railBody = document.getElementById("rail-body");
const railCount = document.getElementById("rail-count");
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
    setReferences(null, "As fontes que embasarem a resposta aparecerão aqui.");
    autoResize();
    questionEl.focus();
}

/**
 * Atualiza a trilha de referências (coluna da direita) com um widget por fonte
 * da resposta mais recente. Com `sources` nulo/vazio, mostra a mensagem de
 * espaço reservado passada em `placeholder`.
 */
function setReferences(sources, placeholder = "Esta resposta não citou fontes específicas.") {
    if (!sources || !sources.length) {
        railCount.hidden = true;
        railCount.textContent = "";
        railBody.innerHTML = `<p class="rail-empty">${escapeHtml(placeholder)}</p>`;
        return;
    }

    railCount.hidden = false;
    railCount.textContent = String(sources.length);
    railBody.innerHTML = "";

    sources.forEach((s, i) => {
        const card = document.createElement("article");
        card.className = "ref-card";
        card.setAttribute("data-tip", s.source);
        card.innerHTML =
            `<div class="ref-head">` +
            `<span class="ref-index">${i + 1}</span>` +
            `<span class="ref-title">${escapeHtml(s.source)}</span>` +
            `</div>` +
            `<div class="ref-meta">${escapeHtml(s.folder)} · ${escapeHtml(s.location || "trecho")}</div>` +
            (s.snippet
                ? `<div class="ref-snippet">${escapeHtml(s.snippet)}</div>`
                : "");
        railBody.appendChild(card);
    });
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
    setReferences(null, "Buscando referências…");

    const bot = createBotMessage();

    try {
        await api.askStream(q, folder, source, {
            onToken: (text) => bot.appendText(text),
            onDone: (sources, scope) => bot.finalize(sources, scope),
            onError: (err) => bot.fail(err.message),
        });
    } catch (err) {
        bot.fail(err.message);
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

function scopeText(scope) {
    if (scope === "todas") return "Todos os assuntos";
    if (scope.includes(" / ")) {
        const [f, a] = scope.split(" / ");
        return `Assunto: ${f} · Artigo: ${a}`;
    }
    return `Assunto: ${scope}`;
}

/**
 * Cria a mensagem do assistente já visível (com indicador de digitação) e
 * devolve helpers para preenchê-la enquanto a resposta chega em streaming.
 */
function createBotMessage() {
    const row = document.createElement("div");
    row.className = "msg-row assistant";

    const avatar = document.createElement("div");
    avatar.className = "msg-avatar";
    avatar.textContent = "◆";

    const content = document.createElement("div");
    content.className = "msg-content";

    const typing = document.createElement("div");
    typing.className = "typing";
    typing.innerHTML = "<span></span><span></span><span></span>";
    content.appendChild(typing);

    const body = document.createElement("div");
    body.className = "msg-text";

    row.append(avatar, content);
    messagesEl.appendChild(row);
    scrollToBottom();

    let started = false;
    let rawText = "";

    function ensureStarted() {
        if (started) return;
        typing.remove();
        content.appendChild(body);
        started = true;
    }

    return {
        appendText(text) {
            ensureStarted();
            rawText += text;
            body.innerHTML = renderMarkdown(rawText);
            scrollToBottom();
        },
        finalize(sources, scope) {
            ensureStarted();
            if (scope) {
                const tag = document.createElement("div");
                tag.className = "scope-tag";
                tag.textContent = scopeText(scope);
                content.insertBefore(tag, body);
            }
            if (sources && sources.length) {
                const box = document.createElement("div");
                box.className = "msg-sources";

                const lbl = document.createElement("span");
                lbl.className = "lbl";
                lbl.textContent =
                    sources.length === 1 ? "1 fonte:" : `${sources.length} fontes:`;
                box.appendChild(lbl);

                sources.forEach((s) => {
                    const chip = document.createElement("span");
                    chip.className = "src-chip";
                    chip.setAttribute("data-tip", s.source);
                    chip.textContent = s.source;
                    box.appendChild(chip);
                });
                content.appendChild(box);
            }
            setReferences(sources);
            scrollToBottom();
        },
        fail(message) {
            ensureStarted();
            body.textContent = `Erro: ${message}`;
            setReferences(null, "Não foi possível obter referências para esta resposta.");
        },
    };
}

function scrollToBottom() {
    const scroll = document.getElementById("chat-scroll");
    scroll.scrollTop = scroll.scrollHeight;
}
