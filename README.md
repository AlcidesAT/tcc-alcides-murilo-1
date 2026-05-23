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
| Frontend | HTML, CSS e JavaScript puros |

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
2. Acesse `http://127.0.0.1:8000` no navegador.
3. No painel lateral, clique em **"Clique ou arraste um arquivo aqui"** e escolha um artigo (PDF/MD/TXT).
4. Clique em **"Indexar artigo"** e aguarde a confirmação (a primeira indexação pode demorar enquanto os embeddings são calculados).
5. Repita para quantos artigos quiser. Eles aparecerão na lista "Artigos indexados".
6. Digite uma pergunta no campo inferior e pressione **Enter** ou clique em **Perguntar**.
7. A resposta aparecerá com os **trechos-fonte** que embasaram a geração — exatamente o comportamento de rastreabilidade citado na proposta do TCC.

## Endpoints da API

| Método | Rota | Descrição |
| --- | --- | --- |
| `GET` | `/api/health` | Verifica se a API está no ar. |
| `GET` | `/api/documents` | Lista artigos indexados e contagem de chunks. |
| `POST` | `/api/upload` | Recebe um arquivo (`multipart/form-data`) e o indexa. |
| `DELETE` | `/api/documents/{nome}` | Remove um artigo do índice. |
| `POST` | `/api/ask` | Recebe `{"question": "..."}` e devolve `{answer, sources}`. |

A documentação interativa fica em <http://127.0.0.1:8000/docs>.

## Estrutura de pastas

```
tcc-alcides-murilo-1/
├── backend/
│   ├── config.py
│   ├── document_processor.py
│   ├── rag_service.py
│   ├── main.py
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
├── data/
│   ├── documents/      # PDFs/MDs/TXTs enviados
│   └── vectorstore/    # Índice Chroma persistente
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
