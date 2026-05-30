/**
 * Card "1. Criar pastas".
 *
 * Responsável por:
 *  - Criar pasta nova (form sempre visível)
 *  - Listar pastas existentes (com seus artigos como sub-itens)
 *  - Remover pastas e artigos individuais
 *  - Recarregar o estado global (state.js) — é a única fonte de verdade
 *    quanto a "que pastas/documentos existem"
 */

import * as api from "./api.js";
import { setData } from "./state.js";

const folderListEl = document.getElementById("folder-list");
const refreshBtn = document.getElementById("refresh-btn");
const newFolderName = document.getElementById("new-folder-name");
const newFolderSave = document.getElementById("new-folder-save");

const collapsed = new Set();

export async function loadFolders() {
    const [folders, documents] = await Promise.all([
        api.listFolders().catch(() => []),
        api.listDocuments().catch(() => []),
    ]);
    setData(folders, documents);
}

export function initFolders() {
    refreshBtn.addEventListener("click", loadFolders);
    newFolderSave.addEventListener("click", createFolder);
    newFolderName.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            createFolder();
        }
    });
}

export function renderFolders({ folders, documentsByFolder }) {
    folderListEl.innerHTML = "";
    if (!folders.length) {
        const p = document.createElement("p");
        p.className = "empty";
        p.textContent = "Nenhum assunto criado ainda.";
        folderListEl.appendChild(p);
        return;
    }

    folders.forEach((f) => {
        folderListEl.appendChild(buildFolderGroup(f, documentsByFolder[f.folder] || []));
    });
}

function buildFolderGroup(folder, docs) {
    const group = document.createElement("div");
    group.className = "folder-group";
    if (collapsed.has(folder.folder)) group.classList.add("collapsed");

    const header = document.createElement("div");
    header.className = "folder-header";

    const toggle = document.createElement("span");
    toggle.className = "folder-toggle";
    toggle.textContent = "▼";

    const name = document.createElement("span");
    name.className = "folder-name";
    name.title = folder.folder;
    name.textContent = folder.folder;

    const meta = document.createElement("span");
    meta.className = "folder-meta";
    meta.textContent = `${folder.documents} art.`;

    const del = document.createElement("button");
    del.className = "folder-del";
    del.textContent = "🗑";
    del.title = "Excluir assunto";
    del.addEventListener("click", (e) => {
        e.stopPropagation();
        handleDeleteFolder(folder.folder, folder.documents);
    });

    header.append(toggle, name, meta, del);
    header.addEventListener("click", () => toggleCollapsed(group, folder.folder));

    const list = document.createElement("ul");
    list.className = "folder-docs";
    if (docs.length === 0) {
        const li = document.createElement("li");
        li.className = "empty-folder";
        li.textContent = "Vazio — envie artigos para este assunto.";
        list.appendChild(li);
    }
    docs.forEach((d) => list.appendChild(buildDocItem(d)));

    group.append(header, list);
    return group;
}

function buildDocItem(doc) {
    const li = document.createElement("li");
    const name = document.createElement("span");
    name.className = "doc-name";
    name.title = doc.source;
    name.textContent = doc.source;
    const meta = document.createElement("span");
    meta.className = "doc-meta";
    meta.textContent = `${doc.chunks} trechos`;
    const del = document.createElement("button");
    del.className = "del-btn";
    del.textContent = "✕";
    del.title = "Remover artigo";
    del.addEventListener("click", () => handleDeleteDoc(doc.folder, doc.source));
    li.append(name, meta, del);
    return li;
}

function toggleCollapsed(group, name) {
    if (collapsed.has(name)) {
        collapsed.delete(name);
        group.classList.remove("collapsed");
    } else {
        collapsed.add(name);
        group.classList.add("collapsed");
    }
}

async function createFolder() {
    const name = newFolderName.value.trim();
    if (!name) {
        newFolderName.focus();
        return;
    }
    newFolderSave.disabled = true;
    try {
        await api.createFolder(name);
        newFolderName.value = "";
        await loadFolders();
    } catch (err) {
        alert(err.message);
    } finally {
        newFolderSave.disabled = false;
    }
}

async function handleDeleteFolder(name, docCount) {
    const msg = docCount
        ? `Excluir o assunto "${name}" e seus ${docCount} artigo(s)?\nEsta ação não pode ser desfeita.`
        : `Excluir o assunto "${name}"?`;
    if (!confirm(msg)) return;
    try {
        await api.deleteFolder(name);
        await loadFolders();
    } catch (err) {
        alert(err.message);
    }
}

async function handleDeleteDoc(folder, source) {
    if (!confirm(`Remover "${source}" do assunto "${folder}"?`)) return;
    try {
        await api.deleteDocument(folder, source);
        await loadFolders();
    } catch (err) {
        alert(err.message);
    }
}
