/**
 * Camada HTTP — concentra todas as chamadas ao backend.
 *
 * Injeta automaticamente o token JWT (quando disponível) no cabeçalho
 * Authorization de cada requisição.
 */

const API = "";

function getToken() {
    return localStorage.getItem("auth_token");
}

async function request(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    const token = getToken();
    if (token) {
        headers["Authorization"] = `Bearer ${token}`;
    }

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
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
    });
}

export async function deleteFolder(folder) {
    return request(`/api/folders/${encodeURIComponent(folder)}`, { method: "DELETE" });
}

export async function deleteDocument(folder, source) {
    const path =
        `/api/folders/${encodeURIComponent(folder)}` +
        `/documents/${encodeURIComponent(source)}`;
    return request(path, { method: "DELETE" });
}

export async function uploadFile(folder, file) {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("folder", folder);
    return request("/api/upload", { method: "POST", body: fd });
}

export async function ask(question, folder, source) {
    return request("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, folder, source }),
    });
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export async function login(email, password) {
    return request("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
    });
}

export async function register(name, email, password) {
    return request("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, password }),
    });
}

export async function getMe() {
    return request("/api/auth/me");
}
