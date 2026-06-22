/**
 * Tooltip ("balão") global e leve.
 *
 * Qualquer elemento com o atributo `data-tip="texto"` exibe o balão ao passar
 * o mouse. O balão é anexado ao <body> e posicionado via `position: fixed`,
 * de modo que nunca é cortado por contêineres com rolagem (como a trilha de
 * referências). Usado para mostrar o nome completo de artigos truncados.
 */

let tipEl = null;

function ensureTip() {
    if (!tipEl) {
        tipEl = document.createElement("div");
        tipEl.className = "tooltip";
        document.body.appendChild(tipEl);
    }
    return tipEl;
}

function show(target) {
    const text = target.getAttribute("data-tip");
    if (!text) return;

    const tip = ensureTip();
    tip.textContent = text;
    tip.classList.add("show");

    const r = target.getBoundingClientRect();
    const tr = tip.getBoundingClientRect();

    let left = r.left + r.width / 2 - tr.width / 2;
    left = Math.max(8, Math.min(left, window.innerWidth - tr.width - 8));

    // Acima do elemento; se não couber, vira para baixo.
    let top = r.top - tr.height - 8;
    if (top < 8) top = r.bottom + 8;

    tip.style.left = `${left}px`;
    tip.style.top = `${top}px`;
}

function hide() {
    if (tipEl) tipEl.classList.remove("show");
}

export function initTooltips() {
    document.addEventListener("mouseover", (e) => {
        const target = e.target.closest("[data-tip]");
        if (target) show(target);
    });
    document.addEventListener("mouseout", (e) => {
        if (e.target.closest("[data-tip]")) hide();
    });
    // Esconde ao rolar (a posição fixa ficaria deslocada).
    document.addEventListener("scroll", hide, true);
}
