/**
 * Ponto de entrada da aplicação.
 *
 * Aqui as três seções (pastas, upload e chat) são inicializadas e conectadas
 * ao estado global. O fluxo é:
 *
 *   1. Cada módulo "init*" registra seus eventos de UI.
 *   2. `subscribe(...)` faz upload e chat reagirem a mudanças nos dados.
 *   3. `loadFolders()` faz a primeira carga, disparando os subscribers.
 */

import { subscribe } from "./state.js";
import { initAuth } from "./auth.js";
import { initTooltips } from "./tooltip.js";
import { initFolders, loadFolders, renderFolders } from "./folders.js";
import { initUpload, updateFolderSelector } from "./upload.js";
import { initChat, updateScopeSelectors } from "./chat.js";

initAuth();
initTooltips();
initFolders();
initUpload();
initChat();

subscribe((state) => {
    renderFolders(state);
    updateFolderSelector(state);
    updateScopeSelectors(state);
});

loadFolders();
