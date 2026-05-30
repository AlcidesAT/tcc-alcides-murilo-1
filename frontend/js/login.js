import { login, register } from "./api.js";

// Tab switching
const tabs = document.querySelectorAll(".auth-tab");
const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");

tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
        tabs.forEach((t) => t.classList.remove("active"));
        tab.classList.add("active");
        const target = tab.dataset.tab;
        loginForm.hidden = target !== "login";
        registerForm.hidden = target !== "register";
    });
});

// Redirect if already logged in
if (localStorage.getItem("auth_token")) {
    window.location.replace("/");
}

// Login
loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = document.getElementById("login-btn");
    const errEl = document.getElementById("login-error");
    const email = document.getElementById("login-email").value.trim();
    const password = document.getElementById("login-password").value;

    btn.disabled = true;
    btn.textContent = "Entrando…";
    errEl.hidden = true;

    try {
        const data = await login(email, password);
        localStorage.setItem("auth_token", data.token);
        localStorage.setItem("auth_user", JSON.stringify(data.user));
        window.location.replace("/");
    } catch (err) {
        errEl.textContent = err.message;
        errEl.hidden = false;
        btn.disabled = false;
        btn.textContent = "Entrar";
    }
});

// Register
registerForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = document.getElementById("register-btn");
    const errEl = document.getElementById("register-error");
    const name = document.getElementById("reg-name").value.trim();
    const email = document.getElementById("reg-email").value.trim();
    const password = document.getElementById("reg-password").value;
    const confirm = document.getElementById("reg-confirm").value;

    if (password !== confirm) {
        errEl.textContent = "As senhas não coincidem.";
        errEl.hidden = false;
        return;
    }

    btn.disabled = true;
    btn.textContent = "Criando conta…";
    errEl.hidden = true;

    try {
        const data = await register(name, email, password);
        localStorage.setItem("auth_token", data.token);
        localStorage.setItem("auth_user", JSON.stringify(data.user));
        window.location.replace("/");
    } catch (err) {
        errEl.textContent = err.message;
        errEl.hidden = false;
        btn.disabled = false;
        btn.textContent = "Criar conta";
    }
});
