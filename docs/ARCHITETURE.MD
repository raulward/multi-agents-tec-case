# ARCHITETURE

## 1) Visao Geral do Sistema
Este projeto implementa uma API de Financial QA com arquitetura multi-agentes e camada RAG.

Objetivos principais:
- Ingerir fontes (PDF/HTML), enriquecer metadados e indexar em ChromaDB.
- Responder perguntas com workflow LangGraph e agentes especializados.
- Expor rastreabilidade de execucao (`trace`) e custo/token por execucao.

## 2) Componentes Principais

### 2.1 API (FastAPI)
- `app/main.py`: inicializa `WorkflowDependencies` no lifespan e compila workflow (`build_workflows`).
- `app/api/v1/health.py`: `GET /v1/health` (status, chunks indexados, modelo).
- `app/api/v1/query.py`: `POST /v1/query`.
- `app/api/v1/ingest.py`: `POST /v1/ingest`.

### 2.2 Servicos de Aplicacao
- `app/services/query_service.py`
  - Monta estado inicial (`create_initial_state`).
  - Executa `workflow_app.stream(...)`.
  - Mapeia `final_state` para `QueryResponse`.
- `app/services/ingestion_service.py`
  - Resolve fontes da request ou `data/ingestion/source_catalog.json`.
  - Aciona pipeline deterministica via `run_sources(...)`.

### 2.3 Workflow Multi-Agentes (LangGraph)
- `app/ai/workflows/workflow.py`
  - Grafo linear: `orchestrate -> retrieve -> run_agents -> finalize -> END`.
- `app/ai/workflows/nodes.py`
  - `orchestrate`: seleciona agentes e filtros de busca.
  - `retrieve`: recupera chunks no RAG.
  - `run_agents`: executa `extractor`/`sentiment` (quando roteados) e sempre `qa`.
  - `finalize`: fecha resposta final e consolida trace/custos.
- `app/ai/workflows/state.py`: define contrato do `AgentState`.

### 2.4 Agentes LLM
- `OrchestratorAgent`: gera plano de busca e agentes alvo.
- `ExtractorAgent`: extrai metricas estruturadas dos documentos recuperados.
- `SentimentAgent`: gera analise de risco/sentimento.
- `QAAgent`: compoe resposta final com citacoes e confianca.

### 2.5 Camada RAG
- `app/rag/rag_service.py`: fachada de retrieval/indexacao e deduplicacao de docs.
- `app/rag/rag_processor.py`: integracao com ChromaDB.
  - `chromadb.PersistentClient`.
  - Collection com `metadata={"hnsw:space": "cosine"}`.
  - Embeddings `text-embedding-3-small`.

### 2.6 Pipeline de Ingestao
- `app/rag/ingestion/runner.py`: pipeline principal por fonte:
  1. fetch (`fetch_url`)
  2. parse para markdown (`parse_pdf_to_markdown` / `parse_html_to_markdown`)
  3. enriquecimento LLM (`enrich_markdown_with_llm`)
  4. chunking (`Chunker`)
  5. indexacao (`deps.rag.add_document`)
  6. persistencia de markdown em `data/processed`
- `app/rag/ingestion/dispatcher.py` e `app/rag/ingestion/detector.py` estao marcados como legados (nao usados no fluxo atual).

### 2.7 UI
- `ui.py` (Streamlit) consome a API para rodar ingestao e consultas.

## 3) Fluxo de Query (`POST /v1/query`)
1. Requisicao chega em `app/api/v1/query.py`.
2. `QueryService.run` cria `run_id` e `initial_state`.
3. Workflow executa:
   - `orchestrate`: decide `search_queries` + `selected_agents`.
   - `retrieve`: busca chunks no Chroma (com fallback sem filtro quando necessario).
   - `run_agents`: roda agentes em ordem dinamica e depois `qa`.
   - `finalize`: compoe `final_answer` e registra metadados finais.
4. Service converte estado final para `QueryResponse`:
   - `final_answer`, `confidence`, `citations`, `extracted_metrics`, `sentiment_analysis`, `routing`, `trace`.

## 4) Fluxo de Ingestao (`POST /v1/ingest`)
1. Requisicao chega em `app/api/v1/ingest.py`.
2. `IngestionService.ingest` resolve lista de fontes:
   - `req.sources` ou
   - catalogo `data/ingestion/source_catalog.json`.
3. `run_sources` processa cada item com controle de falhas por etapa.
4. Chunks sao indexados no Chroma e markdown salvo em `DATA_DIR`.
5. API retorna agregados: `total_requested`, `total_downloaded`, `total_failed`, `failures`.

## 5) Dependencias e Configuracao
- `app/ai/workflows/workflow_dependencies.py`
  - Singleton de dependencias.
  - Inicializa `ChatOpenAI` (`MODEL_NAME`, default `gpt-4o-mini`).
  - Inicializa `RAGProcessor`/`RagService`.
  - Monta `agent_registry`.
- `app/core/config.py`
  - Variaveis relevantes: `OPENAI_API_KEY`, `CHROMA_PERSIST_DIR`, `CHROMA_COLLECTION`, `DATA_DIR`, `SEARCH_URLS`, `MODEL_NAME`.

## 6) Persistencia e Fronteiras Externas
- Banco vetorial: ChromaDB persistente em `./chroma_db`.
- Artefatos processados: markdown em `./data/processed`.
- Integracoes externas:
  - OpenAI (chat + embeddings)
  - URLs de origem para ingestao (HTTP GET)

## 7) Observabilidade e Confiabilidade
- Cada query recebe `run_id` unico.
- `agent_trace` registra etapas, latencia (`dt_ms`), metadados e erros por passo.
- Custos/tokens acumulados por agente em `WorkflowNodes`.
- Ingestao registra eventos estruturados por etapa e falhas por fonte/step.

## 8) Decisoes e Trade-offs
- Similaridade vetorial: cosseno (`hnsw:space=cosine`) para embeddings OpenAI.
- Orquestracao por LLM (vs roteamento deterministico): melhor cobertura para queries complexas.
- Pipeline de ingestao atual prioriza fluxo deterministico (`runner.py`) e deixa dispatcher/detector como legado.


