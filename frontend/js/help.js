/**
 * Expansivo "Como perguntar".
 *
 * Orienta o que e como perguntar e mostra os temas do acervo, com exemplos que
 * preenchem o campo de pergunta ao clicar. Os assuntos vêm do estado global;
 * os temas e exemplos abaixo foram conferidos no acervo.
 */

import { displayFolderName } from "./folders.js";

const TOPICS = {
    "ciencia-juridica": {
        themes: "contratos, direitos fundamentais, crimes, direito ambiental e da criança",
        examples: [
            "A castração química é constitucional?",
            "Quais são as competências do conselho tutelar?",
        ],
    },
    "ciencias-agrarias": {
        themes: "milho, soja, alface, adubação, fungicidas e conservação de frutas",
        examples: [
            "Qual o efeito do nitrogênio na cultura do milho?",
            "Como o melão minimamente processado se conservou sob refrigeração?",
        ],
    },
    "ciencias-da-educacao": {
        themes: "educação física, educação infantil, inclusão e relação professor-aluno",
        examples: [
            "Qual a importância da afetividade na relação entre professor e aluno?",
            "Como as atividades lúdicas ajudam na coordenação motora das crianças?",
        ],
    },
    "ciencias-da-vida-e-saude": {
        themes: "enfermagem, psicologia, saúde mental, saúde bucal e qualidade de vida",
        examples: [
            "Quais fatores causam estresse nos profissionais de enfermagem?",
            "Como o consumo de açúcar favorece as cáries?",
        ],
    },
    "ciencias-exatas-e-tecnologicas": {
        themes: "inteligência artificial, arquitetura, design, concreto e segurança de código",
        examples: [
            "Como a inteligência artificial é usada na arquitetura?",
            "Como reaproveitar madeira de descarte em móveis?",
        ],
    },
    "ciencias-sociais": {
        themes: "gestão de pessoas, empresas, gênero e violência",
        examples: [
            "Quais estratégias ajudam a reter talentos em pequenas empresas?",
            "Quais são as causas da rotatividade nas organizações?",
        ],
    },
};

const helpEl = document.getElementById("ask-help");
const topicsEl = document.getElementById("help-topics");
const questionEl = document.getElementById("question");

export function initHelp() {
    topicsEl.addEventListener("click", (e) => {
        const example = e.target.closest(".help-example");
        if (!example) return;
        questionEl.value = example.textContent;
        questionEl.dispatchEvent(new Event("input"));
        helpEl.open = false;
        questionEl.focus();
    });
}

export function renderHelp({ folders }) {
    topicsEl.replaceChildren(...folders.filter((f) => f.documents > 0).map(buildTopic));
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
