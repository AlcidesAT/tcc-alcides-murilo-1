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

export async function ask(question, folder, source) {
    return request("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, folder, source }),
    });
}

/**
 * Versão em streaming de `ask`. Lê uma resposta NDJSON e chama os callbacks:
 *   onToken(text)            — a cada pedaço de texto gerado
 *   onDone(sources, scope)   — ao final, com as fontes e o escopo
 *   onError(error)           — em caso de erro durante a geração
 */
export async function askStream(question, folder, source, { onToken, onDone, onError }) {
    const res = await fetch("/api/ask/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, folder, source }),
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
            else if (msg.type === "done") onDone?.(msg.sources, msg.scope);
            else if (msg.type === "error") onError?.(new Error(msg.detail));
        }
    }
}
