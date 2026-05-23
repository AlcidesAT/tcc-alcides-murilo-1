/**
 * Camada HTTP — concentra todas as chamadas ao backend.
 *
 * Cada função devolve o JSON parseado em caso de sucesso ou lança um Error
 * com a mensagem retornada pelo servidor em caso de falha.
 * Os outros módulos NÃO devem usar `fetch` diretamente — sempre passem por aqui.
 */

const API = "";

async function request(path, options = {}) {
    const res = await fetch(`${API}${path}`, options);
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
    return request(`/api/folders/${encodeURIComponent(folder)}`, {
        method: "DELETE",
    });
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
