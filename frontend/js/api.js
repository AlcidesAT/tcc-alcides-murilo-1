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
// Perfil Administrador
//
// O token de sessão fica no sessionStorage (vale enquanto a aba estiver
// aberta). As rotas de gestão recebem o cabeçalho `X-Admin-Token`.
// ---------------------------------------------------------------------------

const ADMIN_TOKEN_KEY = "tcc_admin_token";

export function getAdminToken() {
    return sessionStorage.getItem(ADMIN_TOKEN_KEY) || "";
}

export function setAdminToken(token) {
    if (token) sessionStorage.setItem(ADMIN_TOKEN_KEY, token);
    else sessionStorage.removeItem(ADMIN_TOKEN_KEY);
}

export function isAdmin() {
    return Boolean(getAdminToken());
}

function adminHeaders(extra = {}) {
    return { ...extra, "X-Admin-Token": getAdminToken() };
}

export async function adminLogin(password) {
    const data = await request("/api/admin/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
    });
    setAdminToken(data.token);
    return data;
}

export function adminLogout() {
    setAdminToken("");
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
        headers: adminHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ name }),
    });
}

export async function deleteFolder(folder) {
    return request(`/api/folders/${encodeURIComponent(folder)}`, {
        method: "DELETE",
        headers: adminHeaders(),
    });
}

export async function deleteDocument(folder, source) {
    const path =
        `/api/folders/${encodeURIComponent(folder)}` +
        `/documents/${encodeURIComponent(source)}`;
    return request(path, { method: "DELETE", headers: adminHeaders() });
}

export async function uploadFile(folder, file) {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("folder", folder);
    return request("/api/upload", {
        method: "POST",
        headers: adminHeaders(),
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
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, folder, source, history }),
    });
}

/**
 * Versão em streaming de `ask`. Lê uma resposta NDJSON e chama os callbacks:
 *   onMeta(meta)     — antes da geração: pergunta reescrita pela memória
 *   onToken(text)    — a cada pedaço de texto gerado
 *   onDone(result)   — ao final: { sources, scope, evaluation, model, ... }
 *   onError(error)   — em caso de erro durante a geração
 */
export async function askStream(question, folder, source, history, { onMeta, onToken, onDone, onError }) {
    const res = await fetch("/api/ask/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
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
// Avaliação da precisão das respostas
// ---------------------------------------------------------------------------

export async function sendEvaluation(payload) {
    return request("/api/evaluations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
}

export async function getEvaluationSummary() {
    return request("/api/evaluations/summary", { headers: adminHeaders() });
}

/** Baixa o CSV de avaliações (precisa do cabeçalho de admin, por isso via fetch). */
export async function downloadEvaluationsCsv() {
    const res = await fetch("/api/evaluations/export", { headers: adminHeaders() });
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
    a.download = "avaliacoes-respostas.csv";
    a.click();
    URL.revokeObjectURL(url);
}
