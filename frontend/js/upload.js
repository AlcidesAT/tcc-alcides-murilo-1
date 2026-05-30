/**
 * Card "2. Enviar artigos".
 *
 * Responsável por:
 *  - Listar as pastas existentes no seletor de destino
 *  - Aceitar até MAX_FILES arquivos (clique ou drag-and-drop)
 *  - Enviar os arquivos um a um para o backend, mostrando progresso individual
 *  - Pedir ao módulo de pastas que recarregue a lista após cada batch
 */

import * as api from "./api.js";
import { loadFolders } from "./folders.js";

const MAX_FILES = 10;

const fileInput = document.getElementById("file-input");
const dropZone = document.getElementById("drop-zone");
const dropText = document.getElementById("drop-text");
const uploadBtn = document.getElementById("upload-btn");
const uploadStatus = document.getElementById("upload-status");
const folderSelect = document.getElementById("folder-select");
const selectedBox = document.getElementById("selected-files");
const selectedCount = document.getElementById("selected-count");
const selectedList = document.getElementById("selected-list");

let selectedFiles = [];

export function initUpload() {
    fileInput.addEventListener("change", (e) => {
        handleFiles(e.target.files);
        fileInput.value = "";
    });
    setupDragDrop();
    uploadBtn.addEventListener("click", handleUpload);
    folderSelect.addEventListener("change", updateUploadButtonState);
}

export function updateFolderSelector({ folders }) {
    const prev = folderSelect.value;
    folderSelect.innerHTML = "";

    if (!folders.length) {
        const opt = document.createElement("option");
        opt.value = "";
        opt.textContent = "(crie um assunto)";
        folderSelect.appendChild(opt);
        folderSelect.disabled = true;
    } else {
        folders.forEach((f) => {
            const opt = document.createElement("option");
            opt.value = f.folder;
            opt.textContent = `${f.folder} (${f.documents} art.)`;
            folderSelect.appendChild(opt);
        });
        folderSelect.disabled = false;
        folderSelect.value = folders.some((f) => f.folder === prev)
            ? prev
            : folders[0].folder;
    }
    updateUploadButtonState();
}

function setupDragDrop() {
    ["dragenter", "dragover"].forEach((ev) =>
        dropZone.addEventListener(ev, (e) => {
            e.preventDefault();
            dropZone.classList.add("dragover");
        })
    );
    ["dragleave", "drop"].forEach((ev) =>
        dropZone.addEventListener(ev, (e) => {
            e.preventDefault();
            dropZone.classList.remove("dragover");
        })
    );
    dropZone.addEventListener("drop", (e) => {
        if (e.dataTransfer?.files?.length) handleFiles(e.dataTransfer.files);
    });
}

function setStatus(text, kind = "") {
    uploadStatus.textContent = text;
    uploadStatus.className = "status " + kind;
}

function updateUploadButtonState() {
    uploadBtn.disabled =
        !selectedFiles.length || !folderSelect.value || folderSelect.disabled;
}

function handleFiles(fileListLike) {
    const incoming = Array.from(fileListLike || []);
    if (!incoming.length) return;

    const merged = [...selectedFiles.map((e) => e.file), ...incoming];
    const seen = new Set();
    const unique = [];
    for (const f of merged) {
        const key = `${f.name}::${f.size}`;
        if (seen.has(key)) continue;
        seen.add(key);
        unique.push(f);
    }

    if (unique.length > MAX_FILES) {
        setStatus(
            `Limite de ${MAX_FILES} arquivos por vez. Os primeiros ${MAX_FILES} foram mantidos.`,
            "error"
        );
        unique.length = MAX_FILES;
    } else {
        setStatus("");
    }

    selectedFiles = unique.map((file) => ({
        file,
        status: "",
        statusText: "aguardando",
    }));
    renderSelected();
    updateUploadButtonState();
}

function renderSelected() {
    if (!selectedFiles.length) {
        selectedBox.hidden = true;
        selectedList.innerHTML = "";
        dropText.textContent = "Arraste ou clique — PDF, MD, TXT (máx. 10)";
        return;
    }
    selectedBox.hidden = false;
    selectedCount.textContent =
        selectedFiles.length === 1
            ? "1 arquivo selecionado"
            : `${selectedFiles.length} arquivos selecionados`;
    selectedList.innerHTML = "";
    selectedFiles.forEach((entry) => {
        const li = document.createElement("li");
        li.className = entry.status || "";
        const name = document.createElement("span");
        name.className = "fname";
        name.title = entry.file.name;
        name.textContent = entry.file.name;
        const status = document.createElement("span");
        status.className = "fstatus";
        status.textContent = entry.statusText || "aguardando";
        li.append(name, status);
        selectedList.appendChild(li);
    });
    dropText.textContent = `${selectedFiles.length}/${MAX_FILES} arquivos prontos`;
}

async function uploadOne(folder, entry) {
    entry.status = "";
    entry.statusText = "enviando…";
    renderSelected();
    try {
        const data = await api.uploadFile(folder, entry.file);
        entry.status = "done";
        entry.statusText = `${data.chunks_indexed} trechos`;
        return { ok: true };
    } catch (err) {
        entry.status = "error";
        entry.statusText = "erro";
        return { ok: false, error: err.message };
    } finally {
        renderSelected();
    }
}

async function handleUpload() {
    if (!selectedFiles.length) return;
    const folder = folderSelect.value;
    if (!folder) {
        setStatus("Selecione um assunto de destino.", "error");
        return;
    }

    uploadBtn.disabled = true;
    setStatus(`Indexando ${selectedFiles.length} arquivo(s)…`, "");

    let ok = 0;
    let err = 0;
    for (const entry of selectedFiles) {
        const result = await uploadOne(folder, entry);
        if (result.ok) ok++;
        else err++;
    }

    if (err === 0) {
        setStatus(`${ok} artigo(s) indexado(s) em "${folder}".`, "success");
        setTimeout(() => {
            selectedFiles = [];
            renderSelected();
            setStatus("");
            updateUploadButtonState();
        }, 2500);
    } else {
        setStatus(`${ok} sucesso(s) e ${err} falha(s). Veja a lista acima.`, "error");
        updateUploadButtonState();
    }

    await loadFolders();
}
