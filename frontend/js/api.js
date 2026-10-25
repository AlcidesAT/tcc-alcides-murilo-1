/**
 * Camada HTTP — concentra todas as chamadas ao backend.
 */

const API = "";

async function request(path, options = {}) {
    const headers = { ...(options.headers || {}) };

    const res = await fetch(`${API}${path}`, { ...options, headers });
    let data = null;
    try {
        data = await res.json();
    } catch {
        data = {};
    }
    if (!res.ok) {
        throw new Error(data.detail || `Erro HTTP ${res.status}`);
    }
    return data;
}

// ---------------------------------------------------------------------------
// Login: Participante (login da turma) e Administrador
//
// O token e o perfil ficam no sessionStorage (valem enquanto a aba estiver
// aberta) e o token vai no cabeçalho `X-Auth-Token` de todas as chamadas.
// ---------------------------------------------------------------------------

const AUTH_KEY = "tcc_auth";

function getAuth() {
    try {
        return JSON.parse(sessionStorage.getItem(AUTH_KEY)) || {};
    } catch {
        return {};
    }
}

function setAuth(auth) {
    if (auth?.token) sessionStorage.setItem(AUTH_KEY, JSON.stringify(auth));
    else sessionStorage.removeItem(AUTH_KEY);
}

/** "leitor" (sem login), "participante" ou "admin". */
export function getRole() {
    return getAuth().role || "leitor";
}

export function isAdmin() {
    return getRole() === "admin";
}

export function isParticipant() {
    return getRole() === "participante";
}

function authHeaders(extra = {}) {
    const { token } = getAuth();
    return token ? { ...extra, "X-Auth-Token": token } : { ...extra };
}

export async function login(username, password) {
    const data = await request("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
    });
    setAuth({ token: data.token, role: data.role });
    return data;
}

export async function logout() {
    try {
        await request("/api/auth/logout", { method: "POST", headers: authHeaders() });
    } catch {
        /* sair localmente mesmo se o servidor não responder */
    }
    setAuth(null);
}

/**
 * Confere com o servidor se o login salvo ainda vale (o token do admin muda a
 * cada reinício do servidor). Se não valer, volta ao perfil Leitor.
 */
export async function refreshRole() {
    if (!getAuth().token) return "leitor";
    try {
        const { role } = await request("/api/auth/me", { headers: authHeaders() });
        if (role === "leitor") setAuth(null);
        return role;
    } catch {
        return getRole(); // servidor fora do ar: mantém o que havia
    }
}

// ---------------------------------------------------------------------------
// Folders & documents
// ---------------------------------------------------------------------------

export async function listFolders() {
    const data = await request("/api/folders");
    return data.folders || [];
}

export async function listDocuments() {
    const data = await request("/api/documents");
    return data.documents || [];
}

export async function getArticleContent(folder, source) {
    const path =
        `/api/articles/${encodeURIComponent(folder)}` +
        `/${encodeURIComponent(source)}/content`;
    return request(path);
}

export async function createFolder(name) {
    return request("/api/folders", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ name }),
    });
}

export async function deleteFolder(folder) {
    return request(`/api/folders/${encodeURIComponent(folder)}`, {
        method: "DELETE",
        headers: authHeaders(),
    });
}

export async function deleteDocument(folder, source) {
    const path =
        `/api/folders/${encodeURIComponent(folder)}` +
        `/documents/${encodeURIComponent(source)}`;
    return request(path, { method: "DELETE", headers: authHeaders() });
}

export async function uploadFile(folder, file) {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("folder", folder);
    return request("/api/upload", {
        method: "POST",
        headers: authHeaders(),
        body: fd,
    });
}

/**
 * `history` é a memória da conversa: lista de { question, answer } das
 * perguntas anteriores (o backend usa só as mais recentes).
 */
export async function ask(question, folder, source, history = []) {
    return request("/api/ask", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ question, folder, source, history }),
    });
}

/**
 * Versão em streaming de `ask`. Lê uma resposta NDJSON e chama os callbacks:
 *   onMeta(meta)     — antes da geração: pergunta reescrita pela memória
 *   onToken(text)    — a cada pedaço de texto gerado
 *   onDone(result)   — ao final: { sources, scope, evaluation, model,
 *                      interaction_id, collected, ... }
 *   onError(error)   — em caso de erro durante a geração
 */
export async function askStream(question, folder, source, history, { onMeta, onToken, onDone, onError }) {
    const res = await fetch("/api/ask/stream", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ question, folder, source, history }),
    });

    if (!res.ok || !res.body) {
        let detail = `Erro HTTP ${res.status}`;
        try {
            const data = await res.json();
            detail = data.detail || detail;
        } catch {
            /* corpo não-JSON */
        }
        throw new Error(detail);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        let nl;
        while ((nl = buffer.indexOf("\n")) >= 0) {
            const line = buffer.slice(0, nl).trim();
            buffer = buffer.slice(nl + 1);
            if (!line) continue;

            let msg;
            try {
                msg = JSON.parse(line);
            } catch {
                continue;
            }

            if (msg.type === "token") onToken?.(msg.text);
            else if (msg.type === "meta") onMeta?.(msg);
            else if (msg.type === "done") onDone?.(msg);
            else if (msg.type === "error") onError?.(new Error(msg.detail));
        }
    }
}

// ---------------------------------------------------------------------------
// Avaliação: notas das respostas, questionário e dados coletados
// ---------------------------------------------------------------------------

function postJson(path, payload) {
    return request(path, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(payload),
    });
}

export function sendEvaluation(payload) {
    return postJson("/api/evaluations", payload);
}

export function getSurvey() {
    return request("/api/survey", { headers: authHeaders() });
}

export function sendSurvey(answers, comment) {
    return postJson("/api/survey", { answers, comment });
}

export function getEvaluationSummary() {
    return request("/api/evaluations/summary", { headers: authHeaders() });
}

export function getSurveySummary() {
    return request("/api/survey/summary", { headers: authHeaders() });
}

export function getCollectionSummary() {
    return request("/api/interactions/summary", { headers: authHeaders() });
}

/** Baixa um CSV exclusivo do admin (precisa do cabeçalho, por isso via fetch). */
export async function downloadCsv(path, filename) {
    const res = await fetch(path, { headers: authHeaders() });
    if (!res.ok) {
        let detail = `Erro HTTP ${res.status}`;
        try {
            detail = (await res.json()).detail || detail;
        } catch {
            /* corpo não-JSON */
        }
        throw new Error(detail);
    }
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
}
