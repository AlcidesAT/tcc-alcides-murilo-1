/**
 * Ponto de entrada da aplicação.
 *
 * Aqui as seções (pastas, upload, chat, avaliação e questionário) são inicializadas e
 * conectadas ao estado global. O fluxo é:
 *
 *   1. Cada módulo "init*" registra seus eventos de UI.
 *   2. `subscribe(...)` faz upload e chat reagirem a mudanças nos dados.
 *   3. `loadFolders()` faz a primeira carga, disparando os subscribers.
 */

import { subscribe } from "./state.js";
import { initAuth } from "./auth.js";
import { initTooltips } from "./tooltip.js";
import { initReader } from "./reader.js";
import { initFolders, loadFolders, renderFolders } from "./folders.js";
import { initUpload, updateFolderSelector } from "./upload.js";
import { initChat, updateScopeSelectors } from "./chat.js";
import { initEvaluation } from "./evaluation.js";
import { initSurvey } from "./survey.js";

initAuth();
initTooltips();
initReader();
initFolders();
initUpload();
initChat();
initEvaluation();
initSurvey();

subscribe((state) => {
    renderFolders(state);
    updateFolderSelector(state);
    updateScopeSelectors(state);
});

loadFolders();
