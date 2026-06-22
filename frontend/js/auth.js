/**
 * Perfis de acesso: Leitor (padrão) e Administrador.
 *
 * O Leitor só consulta os artigos indexados (perguntas em linguagem natural).
 * O Administrador, após informar a senha, libera o envio, a organização e a
 * indexação de novos artigos, além da remoção de pastas/artigos.
 *
 * A visibilidade das funcionalidades exclusivas é controlada por uma classe no
 * <body> (`role-admin` / `role-leitor`); o CSS esconde os elementos `.admin-only`
 * e os botões de exclusão para o Leitor.
 */

import * as api from "./api.js";

const profileRole = document.getElementById("profile-role");
const profileBtn = document.getElementById("profile-btn");

const modal = document.getElementById("login-modal");
const passwordInput = document.getElementById("admin-password");
const loginError = document.getElementById("login-error");
const loginSubmit = document.getElementById("login-submit");
const loginCancel = document.getElementById("login-cancel");

export function initAuth() {
    applyRole();

    profileBtn.addEventListener("click", () => {
        if (api.isAdmin()) {
            logout();
        } else {
            openModal();
        }
    });

    loginSubmit.addEventListener("click", submitLogin);
    loginCancel.addEventListener("click", closeModal);
    passwordInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            submitLogin();
        }
    });
    modal.addEventListener("click", (e) => {
        if (e.target === modal) closeModal();
    });
}

/** Reflete o perfil atual no <body> e no rótulo/botão da sidebar. */
function applyRole() {
    const admin = api.isAdmin();
    document.body.classList.toggle("role-admin", admin);
    document.body.classList.toggle("role-leitor", !admin);
    profileRole.textContent = admin ? "Administrador" : "Leitor";
    profileBtn.textContent = admin ? "Sair" : "Entrar como admin";
}

function openModal() {
    loginError.textContent = "";
    passwordInput.value = "";
    modal.hidden = false;
    passwordInput.focus();
}

function closeModal() {
    modal.hidden = true;
}

async function submitLogin() {
    const password = passwordInput.value.trim();
    if (!password) {
        passwordInput.focus();
        return;
    }
    loginSubmit.disabled = true;
    loginError.textContent = "";
    try {
        await api.adminLogin(password);
        closeModal();
        applyRole();
    } catch (err) {
        loginError.textContent = err.message;
        passwordInput.select();
    } finally {
        loginSubmit.disabled = false;
    }
}

function logout() {
    api.adminLogout();
    applyRole();
}
