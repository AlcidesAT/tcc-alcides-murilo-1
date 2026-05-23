/**
 * Estado compartilhado entre os módulos da UI.
 *
 * Quem altera o estado: `folders.js` (após cada loadFolders).
 * Quem reage ao estado: `upload.js` e `chat.js` (atualizam seus seletores
 * quando a lista de pastas/documentos muda).
 *
 * Padrão pub/sub simples: chame `subscribe(fn)` para ser notificado e
 * `setData(...)` para publicar uma nova versão dos dados.
 */

const state = {
    folders: [],
    documents: [],
    documentsByFolder: {},
};

const listeners = new Set();

export function getState() {
    return state;
}

export function setData(folders, documents) {
    state.folders = folders;
    state.documents = documents;
    state.documentsByFolder = {};
    documents.forEach((d) => {
        (state.documentsByFolder[d.folder] ||= []).push(d);
    });
    listeners.forEach((fn) => fn(state));
}

export function subscribe(fn) {
    listeners.add(fn);
    return () => listeners.delete(fn);
}
