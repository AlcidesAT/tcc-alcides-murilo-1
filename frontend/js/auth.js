/**
 * Perfis de acesso: Leitor (padrão), Participante e Administrador.
 *
 * O Leitor só consulta os artigos indexados; nada é registrado.
 * O Participante entra com o login da turma (usado por todos nos testes com
 * usuários): as perguntas, respostas, notas e o questionário vão para o banco.
 * O Administrador envia, organiza e indexa artigos e acessa os dados coletados.
 *
 * A visibilidade das funcionalidades de cada perfil é controlada por uma classe
 * no <body> (`role-leitor` / `role-participante` / `role-admin`); o CSS mostra
 * os elementos `.admin-only` e `.participant-only` só para o perfil certo.
 */

import * as api from "./api.js";

const ROLE_LABELS = {
    leitor: "Leitor",
    participante: "Participante",
    admin: "Administrador",
};

const profileRole = document.getElementById("profile-role");
const profileBtn = document.getElementById("profile-btn");

const modal = document.getElementById("login-modal");
const usernameInput = document.getElementById("login-username");
const passwordInput = document.getElementById("login-password");
const loginError = document.getElementById("login-error");
const loginSubmit = document.getElementById("login-submit");
const loginCancel = document.getElementById("login-cancel");

export async function initAuth() {
    applyRole();

    profileBtn.addEventListener("click", () => {
        if (api.getRole() !== "leitor") {
            logout();
        } else {
            openModal();
        }
    });

    loginSubmit.addEventListener("click", submitLogin);
    loginCancel.addEventListener("click", closeModal);
    [usernameInput, passwordInput].forEach((input) =>
        input.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                submitLogin();
            }
        }),
    );
    modal.addEventListener("click", (e) => {
        if (e.target === modal) closeModal();
    });

    // O login salvo pode ter expirado (ex.: servidor reiniciado).
    const role = await api.refreshRole();
    if (role !== document.body.dataset.role) applyRole();
}

/**
 * Reflete o perfil atual no <body> e no rótulo/botão da sidebar e avisa os
 * demais módulos pelo evento "rolechange" (painel de avaliação, questionário).
 */
function applyRole() {
    const role = api.getRole();
    document.body.dataset.role = role;
    Object.keys(ROLE_LABELS).forEach((r) => document.body.classList.toggle(`role-${r}`, r === role));
    profileRole.textContent = ROLE_LABELS[role];
    profileBtn.textContent = role === "leitor" ? "Entrar" : "Sair";
    document.dispatchEvent(
        new CustomEvent("rolechange", {
            detail: { role, admin: role === "admin", participant: role === "participante" },
        }),
    );
}

function openModal() {
    loginError.textContent = "";
    usernameInput.value = "";
    passwordInput.value = "";
    modal.hidden = false;
    usernameInput.focus();
}

function closeModal() {
    modal.hidden = true;
}

async function submitLogin() {
    const username = usernameInput.value.trim();
    const password = passwordInput.value;
    if (!username) {
        usernameInput.focus();
        return;
    }
    if (!password) {
        passwordInput.focus();
        return;
    }
    loginSubmit.disabled = true;
    loginError.textContent = "";
    try {
        await api.login(username, password);
        closeModal();
        applyRole();
    } catch (err) {
        loginError.textContent = err.message;
        passwordInput.select();
    } finally {
        loginSubmit.disabled = false;
    }
}

async function logout() {
    await api.logout();
    applyRole();
}
