# Sistema Inteligente de Consulta a Artigos Científicos (RAG)

Sistema desenvolvido como Trabalho de Conclusão de Curso (TCC) por **Alcides Antonio Lorenski Neto** e **Murilo Morosini**, Universidade do Oeste de Santa Catarina (Unoesc), São Miguel do Oeste — 2026. Orientadora: Mestra Franciele Carla Petry.

A aplicação permite que o usuário envie artigos científicos (PDF, Markdown ou TXT) e faça perguntas em linguagem natural sobre o conteúdo. As respostas são geradas por um Modelo de Linguagem (LLM) executado localmente via Ollama, fundamentadas em trechos recuperados dos próprios documentos pela arquitetura **Retrieval-Augmented Generation (RAG)**.

## Arquitetura

```
Frontend (HTML/CSS/JS — módulos ES)
   chat · memória da conversa · avaliação (estrelas) · painel admin
        |
        v
FastAPI (backend/main.py)  — só monta o app
   routers/admin.py       login do Administrador
   routers/library.py     assuntos, artigos, upload, remoção
   routers/chat.py        perguntas (com histórico) e streaming NDJSON
   routers/evaluation.py  notas dos usuários, resumo e exportação CSV
        |
        v
rag/service.py (RAGService)
   1. memory.py      resolve perguntas de acompanhamento com o histórico
   2. retrieval.py   busca híbrida: MMR (Chroma) + BM25 (lexical.py), fusão RRF
   3. LLM            resposta com histórico + trechos  (Ollama via LangChain)
   4. evaluation.py  fundamentação da resposta nos trechos
        |
        +-> Embeddings (Ollama: nomic-embed-text) -> Chroma (data/vectorstore)
        +-> PostgreSQL: articles, question_sources, answer_evaluations
```

A separação em dois módulos — **recuperação** e **geração** — segue exatamente a estrutura descrita por Cozman et al. (2025) na proposta do TCC. Na segunda etapa, o backend foi reorganizado em camadas (rotas → serviço → componentes do RAG): o antigo `rag_service.py` virou o pacote `rag/`, com uma única implementação do BM25 (antes repetida em três lugares), e o `main.py` passou a apenas montar a aplicação. As rotas `/api/ask` e `/api/ask/stream` compartilham o mesmo fluxo (`prepare → gerar → avaliar`).

## Tecnologias

| Camada | Ferramenta |
| --- | --- |
| Linguagem principal | Python 3.10+ |
| API HTTP | FastAPI + Uvicorn |
| Orquestração do RAG | LangChain |
| LLM local | Ollama (`llama3.2:1b` por padrão; configurável em `LLM_MODEL`) |
| Embeddings | Ollama (`nomic-embed-text`) |
| Base vetorial | ChromaDB (persistente) |
| Banco de dados | PostgreSQL (metadados, log de fontes e avaliações via SQLAlchemy) |
| Frontend | HTML, CSS e JavaScript puros |

> **Perfis de acesso**: nesta versão o sistema prevê a seleção de dois perfis de usuário — **Leitor** e **Administrador**. O perfil Leitor (padrão) acessa apenas a consulta dos artigos indexados, podendo fazer perguntas em linguagem natural e obter respostas fundamentadas na base de conhecimento. O perfil Administrador possui permissões adicionais: envio, organização e indexação de novos artigos (além da remoção de pastas/artigos). Para entrar como Administrador, clique em **"Entrar como admin"** no rodapé do menu lateral e informe a senha definida em `ADMIN_PASSWORD` (veja `.env.example`). O cadastro de múltiplos usuários no banco (tabela `users`) fica para a **segunda entrega** — por enquanto o acesso de Administrador é protegido por uma única senha.

> **Sobre o "EasyRAG"**: no projeto, a recuperação simples e direta proposta no TCC é implementada com os componentes nativos do LangChain (`Chroma` como vector store + `as_retriever`), formando um pipeline RAG enxuto e fácil de manter. Caso queira substituir por uma biblioteca específica, basta trocar a implementação dentro de [backend/rag/retrieval.py](backend/rag/retrieval.py) — o restante do sistema permanece igual.

## Pré-requisitos

1. **Python 3.10 ou superior** (testado em 3.12).
2. **Ollama** instalado e em execução.
   - Download para Windows: <https://ollama.com/download/windows>
   - Após instalar, abra um terminal e rode:
     ```powershell
     ollama serve
     ```
   - Em outro terminal, baixe os modelos usados:
     ```powershell
     ollama pull llama3.2:1b
     ollama pull nomic-embed-text
     ```
   - O padrão é o modelo leve `llama3.2:1b`. Para respostas mais elaboradas, use `llama3.2` (3B) ou `qwen2.5:3b` definindo `LLM_MODEL` no `.env`.
3. **PostgreSQL 14 ou superior** (para arquivar os metadados dos artigos).
   - Download para Windows: <https://www.postgresql.org/download/windows/>

## Banco de dados (PostgreSQL)

O sistema arquiva os metadados de cada artigo enviado (nome, assunto, tamanho,
nº de trechos indexados e data) na tabela `articles`. O conteúdo vetorizado
continua no ChromaDB; o PostgreSQL guarda o registro/auditoria dos uploads.

1. Crie o banco (uma vez):

   ```powershell
   psql -U postgres -c "CREATE DATABASE tcc_rag;"
   ```

2. Configure a conexão. Copie `.env.example` para `.env` e ajuste o usuário/senha:

   ```powershell
   Copy-Item .env.example .env
   ```

   ```env
   DATABASE_URL=postgresql://postgres:postgres@localhost:5432/tcc_rag
   ```

3. As tabelas são criadas **automaticamente** quando o servidor inicia
   (SQLAlchemy). Se preferir criá-las manualmente, rode o script de esquema:

   ```powershell
   psql -U postgres -d tcc_rag -f database/schema.sql
   ```

> Se o PostgreSQL não estiver acessível, a aplicação continua funcionando para
> upload e consulta — apenas o arquivamento dos metadados é desabilitado (com um
> aviso no console), sem bloquear o RAG.

## Como executar

### Opção A — script automatizado (Windows)

```powershell
./start.ps1
```

O script cria o ambiente virtual `.venv`, instala as dependências, verifica o Ollama e inicia o servidor em `http://127.0.0.1:8000`.

### Opção B — manual

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt

cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Abra o navegador em **<http://127.0.0.1:8000>**.

## Como usar

1. Garanta que o `ollama serve` esteja rodando em outro terminal.
2. Acesse `http://127.0.0.1:8000` no navegador. Você entra como **Leitor**.
3. **Como Leitor**: digite uma pergunta no campo inferior e pressione **Enter** ou clique em enviar. Opcionalmente, restrinja a busca a um assunto/artigo no seletor do topo. A resposta aparece com os **trechos-fonte** que embasaram a geração — o comportamento de rastreabilidade citado na proposta do TCC.
4. **Para enviar/gerenciar artigos** (perfil Administrador): clique em **"Entrar como admin"** no rodapé do menu lateral e informe a senha (`ADMIN_PASSWORD`). As seções de criação de assuntos e envio de artigos passam a aparecer.
5. Como Administrador, crie um assunto, selecione-o, arraste ou clique para escolher os arquivos (PDF/MD/TXT) e clique em **"Indexar artigos"**. A primeira indexação pode demorar enquanto os embeddings são calculados.
6. Para voltar ao perfil Leitor, clique em **"Sair"** no mesmo local.
7. Abaixo de cada resposta há um **selo de confiança** (fundamentação automática) e **estrelas de 1 a 5** para avaliar a precisão. Como Administrador, a seção **"Avaliação das respostas"** do menu lateral mostra os indicadores e exporta tudo em CSV.

## Memória de pergunta

O sistema lembra as perguntas anteriores da conversa, então é possível fazer perguntas de acompanhamento:

> **Usuário:** O que o estudo sobre nitrogênio no milho avaliou?
>
> **Usuário:** E qual foi o delineamento experimental usado?

A interface envia, junto de cada pergunta, os últimos pares pergunta/resposta (o backend continua sem estado). No backend ([backend/rag/memory.py](backend/rag/memory.py)):

1. **Detecção de acompanhamento** — uma heurística identifica perguntas que dependem da conversa: começam com "E…", têm pronomes/demonstrativos ("nelas", "esse problema"), referências genéricas com artigo ("os dados", "a metodologia") ou quase nenhum termo específico. Perguntas completas seguem intactas, sem custo extra.
2. **Reescrita** — o LLM reescreve a pergunta incorporando o tema do histórico. A reescrita só é aceita se trouxer algum termo específico do histórico; modelos pequenos às vezes perdem o assunto ou inventam outro.
3. **Busca multi-consulta** — a busca híbrida usa a reescrita **e** a expansão "pergunta anterior + pergunta atual", fundidas por RRF, o que garante que os termos do tema nunca se percam. Se a reescrita foi rejeitada, usa-se só a expansão.
4. **Geração** — o modelo responde à pergunta **original** do usuário, com o histórico no prompt para entender a que ela se refere; os fatos continuam vindo dos trechos. A reescrita serve só para a busca, porque reescritas de modelos pequenos às vezes desviam o sentido ("quais limitações…" → "quem identificou as limitações…"). O histórico entra no prompt **apenas** em perguntas de acompanhamento; perguntas independentes usam o mesmo prompt da primeira entrega, porque com o histórico presente o modelo tenta ligá-las à conversa anterior.

### Perguntas sobre o acervo

Perguntas como "quais artigos da base falam de tecnologia?" ou "me diga os assuntos relacionados à saúde" pedem a **lista** de artigos, que o modelo não enxerga quando recebe só os trechos recuperados. Quando a pergunta combina um termo de acervo (artigos, assuntos, estudos, base…) com um pedido de listagem (quais, liste, diga, existem…), o prompt ganha o catálogo de títulos por assunto, respeitando o filtro de escopo ([backend/rag/catalog.py](backend/rag/catalog.py)).

Na interface, a faixa acima do campo de pergunta mostra quantas perguntas anteriores estão sendo consideradas, e o botão **"Esquecer"** limpa a memória sem apagar a conversa ("Nova conversa" também limpa). Quando a memória é usada, a resposta indica que se trata de uma pergunta de acompanhamento e mostra como ela foi buscada. Parâmetros: `MEMORY_MAX_TURNS` e `MEMORY_ANSWER_CHARS` em [backend/config.py](backend/config.py).

## Avaliação da precisão das respostas

A precisão é avaliada em três frentes complementares:

**1. Métrica automática por resposta** ([backend/rag/evaluation.py](backend/rag/evaluation.py)). Sem chamadas extras ao modelo, cada resposta recebe:

- **Fundamentação**: fração das frases da resposta cujos termos informativos (comparados por radical) aparecem nos trechos recuperados. Uma frase conta como fundamentada quando ≥ 60% dos seus termos estão no contexto (`EVAL_SENTENCE_SUPPORT`). Frases com números, nomes ou conclusões que não existem em nenhum trecho indicam possível alucinação.
- **Cobertura da pergunta**: fração dos termos da pergunta presentes nos trechos (a recuperação trouxe material sobre o que foi perguntado?).
- **Nível de confiança**: alta (≥ 75%), média (≥ 50%) ou baixa, exibido no selo abaixo da resposta.

> **Limitação conhecida:** a fundamentação verifica se cada frase se apoia em *algum* dos trechos recuperados, não necessariamente no artigo certo. Se o modelo misturar dois artigos (ex.: citar o delineamento de um estudo de alface ao responder sobre o milho), a frase ainda conta como fundamentada. Por isso a métrica automática complementa, e não substitui, a nota humana e o benchmark.

**2. Avaliação humana.** O usuário dá uma nota de 1 (totalmente imprecisa) a 5 (totalmente precisa) e, opcionalmente, um comentário. A nota é gravada na tabela `answer_evaluations` junto do par pergunta/resposta, das fontes, das métricas automáticas e do modelo usado. Isso permite comparar a nota humana com a fundamentação medida e comparar modelos. Diferente do log de fontes, essa tabela guarda o texto da pergunta e da resposta, mas **só quando o usuário escolhe avaliar**. O Administrador vê o resumo no menu lateral (nota média, % de respostas precisas com nota ≥ 4, fundamentação média, distribuição das notas e resultados por modelo) e exporta um CSV pronto para o Excel.

**3. Benchmark offline** ([backend/evaluate.py](backend/evaluate.py)). Um conjunto de perguntas de referência com os artigos esperados ([data/evaluation/perguntas.json](data/evaluation/perguntas.json)) mede, de forma reprodutível:

| Métrica | O que mede |
| --- | --- |
| Acerto@K | algum artigo esperado aparece entre os K trechos recuperados |
| MRR | 1/posição do primeiro trecho de um artigo esperado (média) |
| Precisão das referências | fração das referências exibidas que são artigos esperados |
| Revocação das referências | fração dos artigos esperados que foram exibidos |
| Memória | acerto das perguntas de acompanhamento **sem** e **com** memória |
| Fundamentação (`--gerar`) | média da métrica automática nas respostas geradas |

```powershell
cd backend
python evaluate.py           # recuperação + memória (rápido)
python evaluate.py --gerar   # também gera as respostas e mede a fundamentação
```

Os resultados são impressos e salvos em `data/evaluation/resultados/` com os parâmetros da execução (modelo, `RETRIEVAL_K`, `MMR_LAMBDA`…), para comparar configurações. Para testar outro modelo sem mudar código, defina `LLM_MODEL` no `.env`.

## Endpoints da API

As rotas marcadas com 🔒 exigem o cabeçalho `X-Admin-Token` (obtido em `/api/admin/login`).

| Método | Rota | Descrição |
| --- | --- | --- |
| `GET` | `/api/health` | Verifica se a API está no ar. |
| `POST` | `/api/admin/login` | Recebe `{"password": "..."}` e devolve o token de Administrador. |
| `GET` | `/api/folders` | Lista os assuntos (pastas) e contagem de artigos. |
| `GET` | `/api/documents` | Lista artigos indexados e contagem de chunks. |
| `GET` | `/api/articles` | Lista os artigos arquivados no PostgreSQL (metadados). |
| `POST` | `/api/folders` | 🔒 Cria um novo assunto (pasta). |
| `POST` | `/api/upload` | 🔒 Recebe um arquivo (`multipart/form-data`) e o indexa. |
| `DELETE` | `/api/folders/{folder}/documents/{nome}` | 🔒 Remove um artigo do índice. |
| `DELETE` | `/api/folders/{folder}` | 🔒 Remove um assunto e seus artigos. |
| `POST` | `/api/ask` | Recebe `{"question", "folder"?, "source"?, "history"?: [{question, answer}]}` e devolve `{answer, sources, scope, evaluation, standalone_question, used_memory, …}`. |
| `POST` | `/api/ask/stream` | Igual ao anterior, em streaming NDJSON: eventos `meta` → `token`… → `done`. |
| `POST` | `/api/evaluations` | Registra a nota (1 a 5) e o comentário de uma resposta. |
| `GET` | `/api/evaluations/summary` | 🔒 Indicadores agregados das avaliações. |
| `GET` | `/api/evaluations/export` | 🔒 Todas as avaliações em CSV (`;`, UTF-8 com BOM). |

A documentação interativa fica em <http://127.0.0.1:8000/docs>.

## Estrutura de pastas

```
tcc-alcides-murilo-1/
├── backend/
│   ├── main.py              # monta o app FastAPI (middlewares, rotas, front-end)
│   ├── config.py            # parâmetros, caminhos e variáveis de ambiente
│   ├── database.py          # engine/sessão SQLAlchemy + init_db()
│   ├── models.py            # Article, QuestionSource, AnswerEvaluation
│   ├── schemas.py           # modelos Pydantic de entrada/saída
│   ├── dependencies.py      # get_rag() e require_admin
│   ├── persistence.py       # log de fontes (best-effort)
│   ├── routers/             # admin, library (acervo), chat, evaluation
│   ├── rag/
│   │   ├── service.py       # RAGService: prepare → gerar → avaliar
│   │   ├── retrieval.py     # busca híbrida + referências
│   │   ├── lexical.py       # tokenização e BM25
│   │   ├── memory.py        # memória de pergunta
│   │   ├── catalog.py       # perguntas sobre o acervo (lista de artigos)
│   │   ├── evaluation.py    # fundamentação automática
│   │   └── prompts.py
│   ├── document_processor.py
│   ├── seed_articles.py     # indexa os artigos de data/documents
│   ├── evaluate.py          # benchmark de precisão
│   ├── inspect_chroma.py
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── js/                  # módulos ES (api, chat, memory, feedback, evaluation…)
├── database/
│   └── schema.sql           # esquema SQL (opcional; tabelas criadas pelo app)
├── data/
│   ├── documents/           # PDFs/MDs/TXTs enviados
│   ├── evaluation/          # perguntas de referência (+ resultados/ gerados)
│   └── vectorstore/         # Índice Chroma persistente
├── .env.example             # modelo de configuração (banco, senha, modelos)
├── start.ps1
├── .gitignore
└── README.md
```

## Solução de problemas

- **"Connection refused" ao perguntar**: o Ollama não está rodando. Execute `ollama serve` em outro terminal.
- **"model 'llama3.2:1b' not found"**: rode `ollama pull llama3.2:1b` (e `ollama pull nomic-embed-text`), ou o modelo definido em `LLM_MODEL`.
- **Indexação muito lenta**: a primeira execução baixa modelos e processa todo o PDF. Reduza `CHUNK_SIZE` em `backend/config.py` apenas se for necessário.
- **Resposta diz que "não há informação suficiente"**: o trecho não foi recuperado. Tente reformular a pergunta ou aumentar `RETRIEVAL_K` em `backend/config.py`.

## Próximos passos (alinhados ao cronograma do TCC)

- Aplicar o sistema com a turma de usuários e coletar as avaliações de precisão pela interface (exportáveis em CSV).
- Ampliar o conjunto de perguntas de referência e comparar modelos (`LLM_MODEL`) e parâmetros com `evaluate.py`.
- Avaliar variações do RAG (re-ranking) e comparar as métricas com a configuração atual.
