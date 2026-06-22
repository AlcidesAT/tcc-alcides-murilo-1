# Sistema Inteligente de Consulta a Artigos Científicos (RAG)

Sistema desenvolvido como Trabalho de Conclusão de Curso (TCC) por **Alcides Antonio Lorenski Neto** e **Murilo Morosini**, Universidade do Oeste de Santa Catarina (Unoesc), São Miguel do Oeste — 2026. Orientadora: Mestra Franciele Carla Petry.

A aplicação permite que o usuário envie artigos científicos (PDF, Markdown ou TXT) e faça perguntas em linguagem natural sobre o conteúdo. As respostas são geradas por um Modelo de Linguagem (LLM) executado localmente via Ollama, fundamentadas em trechos recuperados dos próprios documentos pela arquitetura **Retrieval-Augmented Generation (RAG)**.

## Arquitetura

```
Frontend (HTML/CSS/JS)
        |
        v
FastAPI (backend/main.py)
        |
        +-> document_processor.py  -> chunks
        |
        +-> rag_service.py
              |
              +-> Embeddings (Ollama: nomic-embed-text)
              +-> Vector store (Chroma persistente em data/vectorstore)
              +-> LLM (Ollama: llama3.2)  via LangChain
```

A separação em dois módulos — **recuperação** e **geração** — segue exatamente a estrutura descrita por Cozman et al. (2025) na proposta do TCC.

## Tecnologias

| Camada | Ferramenta |
| --- | --- |
| Linguagem principal | Python 3.10+ |
| API HTTP | FastAPI + Uvicorn |
| Orquestração do RAG | LangChain |
| LLM local | Ollama (`llama3.2`) |
| Embeddings | Ollama (`nomic-embed-text`) |
| Base vetorial | ChromaDB (persistente) |
| Banco de dados | PostgreSQL (arquivamento de metadados via SQLAlchemy) |
| Frontend | HTML, CSS e JavaScript puros |

> **Perfis de acesso**: nesta versão o sistema prevê a seleção de dois perfis de usuário — **Leitor** e **Administrador**. O perfil Leitor (padrão) acessa apenas a consulta dos artigos indexados, podendo fazer perguntas em linguagem natural e obter respostas fundamentadas na base de conhecimento. O perfil Administrador possui permissões adicionais: envio, organização e indexação de novos artigos (além da remoção de pastas/artigos). Para entrar como Administrador, clique em **"Entrar como admin"** no rodapé do menu lateral e informe a senha definida em `ADMIN_PASSWORD` (veja `.env.example`). O cadastro de múltiplos usuários no banco (tabela `users`) fica para a **segunda entrega** — por enquanto o acesso de Administrador é protegido por uma única senha.

> **Sobre o "EasyRAG"**: no projeto, a recuperação simples e direta proposta no TCC é implementada com os componentes nativos do LangChain (`Chroma` como vector store + `as_retriever`), formando um pipeline RAG enxuto e fácil de manter. Caso queira substituir por uma biblioteca específica, basta trocar a implementação dentro de [backend/rag_service.py](backend/rag_service.py) — o restante do sistema permanece igual.

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
     ollama pull llama3.2
     ollama pull nomic-embed-text
     ```
   - Se preferir um modelo mais leve, pode usar `llama3.2:1b` ou `qwen2.5:3b` e ajustar `LLM_MODEL` em [backend/config.py](backend/config.py).
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
| `POST` | `/api/ask` | Recebe `{"question": "..."}` e devolve `{answer, sources}`. |

A documentação interativa fica em <http://127.0.0.1:8000/docs>.

## Estrutura de pastas

```
tcc-alcides-murilo-1/
├── backend/
│   ├── config.py            # parâmetros, caminhos e DATABASE_URL
│   ├── database.py          # engine/sessão SQLAlchemy + init_db()
│   ├── models.py            # modelo Article (arquivamento)
│   ├── document_processor.py
│   ├── rag_service.py
│   ├── main.py              # API FastAPI + serve o front-end
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── js/                  # módulos ES (api, app, auth, chat, folders, upload…)
├── database/
│   └── schema.sql           # esquema SQL (opcional; tabelas criadas pelo app)
├── data/
│   ├── documents/           # PDFs/MDs/TXTs enviados
│   └── vectorstore/         # Índice Chroma persistente
├── .env.example             # modelo de configuração (DATABASE_URL)
├── start.ps1
├── .gitignore
└── README.md
```

## Solução de problemas

- **"Connection refused" ao perguntar**: o Ollama não está rodando. Execute `ollama serve` em outro terminal.
- **"model 'llama3.2' not found"**: rode `ollama pull llama3.2` (e `ollama pull nomic-embed-text`).
- **Indexação muito lenta**: a primeira execução baixa modelos e processa todo o PDF. Reduza `CHUNK_SIZE` em `backend/config.py` apenas se for necessário.
- **Resposta diz que "não há informação suficiente"**: o trecho não foi recuperado. Tente reformular a pergunta ou aumentar `RETRIEVAL_K` em `backend/config.py`.

## Próximos passos (alinhados ao cronograma do TCC)

- Aplicar o sistema com a turma de usuários e coletar feedback (relevância, precisão, utilidade).
- Avaliar variações do RAG (re-ranking, hybrid search) e comparar métricas.
- Registrar os resultados parciais para a segunda entrega.
