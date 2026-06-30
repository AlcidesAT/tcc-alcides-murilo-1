/**
 * Leitor de artigos (.md / .txt).
 *
 * Abre um modal mostrando o conteúdo do artigo clicado na trilha de
 * referências. Markdown é renderizado; texto puro é exibido como está.
 */

import * as api from "./api.js";
import { escapeHtml, renderMarkdown } from "./utils.js";

const modal = document.getElementById("reader-modal");
const titleEl = document.getElementById("reader-title");
const bodyEl = document.getElementById("reader-body");
const closeBtn = document.getElementById("reader-close");

export function initReader() {
    closeBtn.addEventListener("click", close);
    modal.addEventListener("click", (e) => {
        if (e.target === modal) close();
    });
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && !modal.hidden) close();
    });
}

export async function openArticle(folder, source) {
    titleEl.textContent = source;
    bodyEl.innerHTML = '<p class="reader-msg">Carregando…</p>';
    modal.hidden = false;

    try {
        const data = await api.getArticleContent(folder, source);
        const isMarkdown = source.toLowerCase().endsWith(".md");
        bodyEl.innerHTML = isMarkdown
            ? renderMarkdown(data.content)
            : `<pre class="reader-pre">${escapeHtml(data.content)}</pre>`;
        bodyEl.scrollTop = 0;
    } catch (err) {
        bodyEl.innerHTML = `<p class="reader-msg error">${escapeHtml(err.message)}</p>`;
    }
}

function close() {
    modal.hidden = true;
    bodyEl.innerHTML = "";
}
