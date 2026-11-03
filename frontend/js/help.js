/**
 * Orientação para perguntar: o expansivo "Como perguntar" e os modelos de
 * pergunta logo acima do campo.
 *
 * O expansivo orienta o que e como perguntar e mostra os temas do acervo, com
 * exemplos. Os modelos seguem o escopo de "Pesquisar em": exemplos de vários
 * assuntos, do assunto escolhido ou, com um artigo escolhido, perguntas sobre
 * ele. Clicar em um exemplo ou modelo só preenche o campo, sem enviar, porque
 * o login da turma tem um número limitado de perguntas. Os assuntos vêm do
 * estado global; os temas e exemplos abaixo foram conferidos no acervo.
 */

import { displayFolderName } from "./folders.js";

const TOPICS = {
    "ciencia-juridica": {
        themes: "contratos, direitos fundamentais, crimes, violência contra a mulher, licitações e direito de família",
        examples: [
            "A castração química em casos de estupro é constitucional?",
            "O pregão eletrônico torna as licitações mais eficientes?",
            "Quais são as vantagens e desvantagens da descriminalização da maconha?",
            "Quais artigos falam sobre alienação parental?",
        ],
    },
    "ciencias-agrarias": {
        themes: "milho, soja, feijão, alface, substratos, adubação e conservação de frutas",
        examples: [
            "Qual foi o efeito do boro na produtividade do feijão?",
            "Como o melão minimamente processado se conservou sob refrigeração?",
            "Quais substratos são melhores para a produção de flores?",
        ],
    },
    "ciencias-da-educacao": {
        themes: "educação física, educação infantil, inclusão, ensino na pandemia e relação professor-aluno",
        examples: [
            "O homeschooling é uma alternativa em tempos de pandemia?",
            "Qual a importância da afetividade na relação entre professor e aluno?",
            "Como as atividades lúdicas ajudam na coordenação motora das crianças?",
        ],
    },
    "ciencias-da-vida-e-saude": {
        themes: "enfermagem, psicologia, saúde mental, saúde bucal e qualidade de vida",
        examples: [
            "Quais fatores causam estresse nos profissionais de enfermagem?",
            "Como o consumo de açúcar favorece o surgimento de cáries?",
            "Como se encontra a saúde mental dos servidores do SUS?",
        ],
    },
    "ciencias-exatas-e-tecnologicas": {
        themes: "inteligência artificial, aplicativos, arquitetura, design e segurança de dados",
        examples: [
            "Como a inteligência artificial é usada na arquitetura?",
            "Como a realidade virtual ajuda no marketing imobiliário?",
            "Quais riscos de privacidade os smartwatches oferecem?",
        ],
    },
    "ciencias-sociais": {
        themes: "gestão de pessoas, empresas, imigração, gênero e violência",
        examples: [
            "Quais estratégias ajudam a reter talentos em pequenas empresas?",
            "Como é o acolhimento dos imigrantes haitianos em São Miguel do Oeste?",
            "O que explica a violência nas torcidas de futebol?",
        ],
    },
};

// Com um artigo escolhido, a busca fica só nele: estas servem para qualquer artigo.
const ARTICLE_MODELS = [
    "Qual é o objetivo deste artigo?",
    "Qual metodologia foi usada no artigo?",
    "Quais foram os principais resultados do artigo?",
    "Quais são as conclusões do artigo?",
];
const MODELS_SHOWN = 3;

const helpEl = document.getElementById("ask-help");
const topicsEl = document.getElementById("help-topics");
const questionEl = document.getElementById("question");
const modelsListEl = document.getElementById("question-models-list");
const modelsMoreBtn = document.getElementById("question-models-more");
const scopeFolder = document.getElementById("scope-folder");
const scopeArticle = document.getElementById("scope-article");
const scopeArticleWrap = document.getElementById("scope-article-wrap");

let folders = [];
let shown = [];

export function initHelp() {
    topicsEl.addEventListener("click", (e) => {
        const example = e.target.closest(".help-example");
        if (!example) return;
        useQuestion(example.textContent);
        helpEl.open = false;
    });
    modelsListEl.addEventListener("click", (e) => {
        const model = e.target.closest(".question-model");
        if (model) useQuestion(model.textContent);
    });
    modelsMoreBtn.addEventListener("click", renderModels);
    // Depois de perguntar, troca os modelos para não sugerir de novo a mesma pergunta.
    document.getElementById("ask-form").addEventListener("submit", renderModels);
    // O chat registra antes o seu "change" do assunto, que acerta a lista de artigos.
    scopeFolder.addEventListener("change", renderModels);
    scopeArticle.addEventListener("change", renderModels);
}

export function renderHelp(state) {
    folders = state.folders.filter((f) => f.documents > 0);
    topicsEl.replaceChildren(...folders.map(buildTopic));
    renderModels();
}

function useQuestion(text) {
    questionEl.value = text;
    questionEl.dispatchEvent(new Event("input"));
    questionEl.focus();
}

/** Troca os modelos na tela, evitando repetir os que já estavam nela. */
function renderModels() {
    const pool = modelPool();
    const fresh = pool.filter((m) => !shown.includes(m.text));
    const picked = pickModels(fresh.length >= MODELS_SHOWN ? fresh : pool);
    shown = picked.map((m) => m.text);
    modelsListEl.replaceChildren(...picked.map(buildModel));
    modelsMoreBtn.hidden = pool.length <= MODELS_SHOWN;
}

function modelPool() {
    const article = scopeFolder.value && !scopeArticleWrap.hidden && scopeArticle.value;
    if (article) return ARTICLE_MODELS.map((text) => ({ text, folder: null }));
    return folders
        .filter((f) => !scopeFolder.value || f.folder === scopeFolder.value)
        .flatMap((f) => (TOPICS[f.folder]?.examples || []).map((text) => ({ text, folder: f.folder })));
}

/** Sorteia os modelos, de assuntos diferentes enquanto houver. */
function pickModels(pool) {
    const shuffled = shuffle(pool);
    const picked = [];
    for (const model of shuffled) {
        const sameFolder = picked.some((p) => p.folder === model.folder);
        if (picked.length < MODELS_SHOWN && !sameFolder) picked.push(model);
    }
    for (const model of shuffled) {
        if (picked.length < MODELS_SHOWN && !picked.includes(model)) picked.push(model);
    }
    return picked;
}

function shuffle(items) {
    const copy = [...items];
    for (let i = copy.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [copy[i], copy[j]] = [copy[j], copy[i]];
    }
    return copy;
}

function buildModel(model) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "question-model";
    button.textContent = model.text;
    if (model.folder) button.title = displayFolderName(model.folder);
    return button;
}

function buildTopic(folder) {
    const topic = TOPICS[folder.folder];

    const box = document.createElement("div");
    box.className = "help-topic";

    const name = document.createElement("div");
    name.className = "help-topic-name";
    const plural = folder.documents === 1 ? "artigo" : "artigos";
    name.textContent = `${displayFolderName(folder.folder)} (${folder.documents} ${plural})`;
    box.appendChild(name);

    if (!topic) return box;

    const themes = document.createElement("div");
    themes.className = "help-topic-themes";
    themes.textContent = topic.themes;
    box.appendChild(themes);

    topic.examples.forEach((text) => {
        const example = document.createElement("button");
        example.type = "button";
        example.className = "help-example";
        example.textContent = text;
        box.appendChild(example);
    });
    return box;
}
