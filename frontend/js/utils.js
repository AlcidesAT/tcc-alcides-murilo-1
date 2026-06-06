/**
 * Funções utilitárias compartilhadas.
 */

export function escapeHtml(s) {
    return String(s)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

/**
 * Converte um subconjunto de Markdown em HTML seguro.
 *
 * Suporta: títulos (#…######), negrito (**), itálico (*), código inline (`),
 * listas com marcador (-/*) e numeradas (1.) e parágrafos. O texto é escapado
 * ANTES de qualquer formatação, então é seguro injetar o resultado via
 * innerHTML mesmo vindo do modelo.
 */
export function renderMarkdown(src) {
    const escape = (s) =>
        String(s)
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;");

    const inline = (s) =>
        escape(s)
            .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
            .replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>")
            .replace(/`([^`]+)`/g, "<code>$1</code>");

    const out = [];
    let listType = null; // "ul" | "ol"

    const closeList = () => {
        if (listType) {
            out.push(`</${listType}>`);
            listType = null;
        }
    };

    for (const raw of String(src).split("\n")) {
        const line = raw.replace(/\s+$/, "");
        const ul = line.match(/^\s*[-*]\s+(.*)$/);
        const ol = line.match(/^\s*\d+\.\s+(.*)$/);
        const h = line.match(/^(#{1,6})\s+(.*)$/);

        if (ul) {
            if (listType !== "ul") {
                closeList();
                out.push("<ul>");
                listType = "ul";
            }
            out.push(`<li>${inline(ul[1])}</li>`);
        } else if (ol) {
            if (listType !== "ol") {
                closeList();
                out.push("<ol>");
                listType = "ol";
            }
            out.push(`<li>${inline(ol[1])}</li>`);
        } else if (h) {
            closeList();
            out.push(`<h4>${inline(h[2])}</h4>`);
        } else if (line.trim() === "") {
            closeList();
        } else {
            closeList();
            out.push(`<p>${inline(line)}</p>`);
        }
    }
    closeList();
    return out.join("");
}
