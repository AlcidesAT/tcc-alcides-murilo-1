import { getMe } from "./api.js";

function escapeHtml(str) {
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
}

function renderUser(area, user) {
    area.innerHTML = `
        <span class="user-greeting">Olá, <strong>${escapeHtml(user.name)}</strong></span>
        <button class="logout-btn" id="logout-btn">Sair</button>
    `;
    document.getElementById("logout-btn").addEventListener("click", () => {
        localStorage.removeItem("auth_token");
        localStorage.removeItem("auth_user");
        renderGuest(area);
    });
}

function renderGuest(area) {
    area.innerHTML = `<a class="login-link" href="/login">Entrar / Cadastrar</a>`;
}

export async function initAuth() {
    const area = document.getElementById("user-area");
    if (!area) return;

    const token = localStorage.getItem("auth_token");
    if (!token) {
        renderGuest(area);
        return;
    }

    try {
        const user = await getMe();
        localStorage.setItem("auth_user", JSON.stringify(user));
        renderUser(area, user);
    } catch {
        localStorage.removeItem("auth_token");
        localStorage.removeItem("auth_user");
        renderGuest(area);
    }
}
