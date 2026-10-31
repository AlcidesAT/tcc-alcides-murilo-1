/**
 * Leitor de artigos.
 *
 * Abre um modal com o artigo clicado no menu de assuntos ou na trilha de
 * referências. Markdown é renderizado, texto puro é exibido como está e PDF
 * abre no visualizador do navegador (na página citada, quando houver).
 */

import * as api from "./api.js";
import { escapeHtml, renderMarkdown } from "./utils.js";

const modal = document.getElementById("reader-modal");
const readerEl = modal.querySelector(".reader");
const titleEl = document.getElementById("reader-title");
const bodyEl = document.getElementById("reader-body");
const newTabLink = document.getElementById("reader-new-tab");
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

/** `location` é o rótulo da referência ("p. 5"), usado para abrir o PDF na página. */
export async function openArticle(folder, source, location = "") {
    titleEl.textContent = source;
    modal.hidden = false;

    const isPdf = source.toLowerCase().endsWith(".pdf");
    readerEl.classList.toggle("reader-pdf", isPdf);
    newTabLink.hidden = !isPdf;

    if (isPdf) {
        const page = /^p\. (\d+)$/.exec(location)?.[1];
        const url = api.articleFileUrl(folder, source) + (page ? `#page=${page}` : "");
        newTabLink.href = url;

        const frame = document.createElement("iframe");
        frame.className = "reader-frame";
        frame.title = source;
        frame.src = url;
        bodyEl.replaceChildren(frame);
        return;
    }

    bodyEl.innerHTML = '<p class="reader-msg">Carregando…</p>';
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
