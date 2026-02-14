# Multi-Agent Financial QA

API de perguntas e respostas financeiras com arquitetura multiagente + RAG.

## O que o projeto faz
- Ingesta fontes PDF/HTML.
- Converte para markdown, enriquece metadados e indexa no ChromaDB.
- Executa workflow com agentes (`orchestrator`, `extractor`, `sentiment`, `qa`) para responder perguntas.
- Expõe rastreabilidade de execução via `trace`.

## Stack
- Python 3.10+
- FastAPI
- LangGraph / LangChain
- OpenAI
- ChromaDB
- Streamlit
- Docker + Docker Compose

## Estrutura principal
- `app/main.py`: inicialização da API e dependências do workflow.
- `app/api/v1`: rotas `health`, `ingest`, `query`.
- `app/services`: serviços de consulta e ingestão.
- `app/ai/workflows`: grafo de execução multiagente.
- `app/rag`: indexação, retrieval e pipeline de ingestão.
- `ui.py`: interface Streamlit.
- `data/ingestion/source_catalog.json`: catálogo padrão de fontes.

## Variáveis de ambiente
Crie um `.env` na raiz com pelo menos:

```env
OPENAI_API_KEY=your_openai_key_here
```

Variáveis opcionais (com defaults em `app/core/config.py`):
- `CHROMA_PERSIST_DIR` (default: `./chroma_db`)
- `CHROMA_COLLECTION` (default: `financial_docs`)
- `DATA_DIR` (default: `./data/processed`)
- `MODEL_NAME` (default: `gpt-4o-mini`)

## Rodar com Docker
```bash
docker compose up --build -d
```

Serviços:
- API: `http://localhost:8000`
- UI: `http://localhost:8501`

Parar:
```bash
docker compose down
```

## Endpoints
### `GET /v1/health`
Retorna status da API e quantidade de chunks indexados.

Exemplo de resposta:
```json
{
  "status": "ok",
  "chunks_indexed": 123,
  "model": "gpt-4o-mini"
}
```

### `POST /v1/ingest`
Inicia ingestão de fontes.

- Corpo vazio `{}`: usa o catálogo `data/ingestion/source_catalog.json`.
- Corpo com `sources`: usa fontes enviadas na request.

Exemplo de request:
```json
{
  "sources": [
    {
      "id": "apple_q4_2024",
      "kind": "pdf",
      "url": "https://example.com/file.pdf"
    }
  ]
}
```

Exemplo de resposta:
```json
{
  "total_requested": 1,
  "total_downloaded": 1,
  "total_failed": 0,
  "failures": []
}
```

### `POST /v1/query`
Executa o workflow multiagente para responder à pergunta.

Exemplo de request:
```json
{
  "query": "Qual foi a margem bruta da Apple no último trimestre?"
}
```

Exemplo de resposta (shape):
```json
{
  "final_answer": "string|null",
  "confidence": 0.0,
  "citations": [],
  "extracted_metrics": {},
  "sentiment_analysis": {},
  "routing": {
    "selected_agents": [],
    "reasoning": "string"
  },
  "trace": []
}
```

## Fluxo resumido
1. `POST /v1/query` cria estado inicial.
2. `orchestrator` decide agentes e filtros.
3. Retrieval busca chunks relevantes no Chroma.
4. Agentes executam (dinâmico) e `qa` consolida resposta.
5. `finalize` monta saída e `trace`.

## Troubleshooting rápido
- Build Docker demorado no primeiro run: normal (download de dependências).
- Erro de conexão Docker no Windows (`dockerDesktopLinuxEngine`): abra o Docker Desktop e valide `docker info`.
- API 500 em query/ingest: valide `OPENAI_API_KEY` no `.env`.
