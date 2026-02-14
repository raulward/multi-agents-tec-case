# Architecture Overview (Template)

## 1) Overview do Sistema
- Protótipo de um sistema multi-agentes capaz de tornar 

## 2) Query Flow
- `POST /v1/query`
- API -> Service -> Workflow -> Agents -> Response
- Fill concrete module calls.

## 3) Ingestion Flow
- `POST /v1/ingest`
- API -> Service -> Dispatcher -> Ingestor -> RAG indexing
- Fill concrete module calls.

## 4) RAG Layer (Simple Split)
- `RagHandler`: external facade used by services/workflows
- `RagIndexer`: ingestion/index operations
- `RagRetrieval`: query/search operations

## 5) PDF Processing Responsibilities
- `PDFProcessor`: extract + normalize text/metadata
- `Chunker`: segment normalized text into chunks

## 6) Decisions & Trade-offs
- Decision 1:
- Decision 2:
- Decision 3:

## 7) LangGraph Flow Diagram
- Output image path: `docs/assets/langgraph_flow.png`
- Embed after generating:
```md
![LangGraph Flow](docs/assets/langgraph_flow.png)
```

## 8) How to Generate LangGraph Image (Objective Steps)
1. Ensure app dependencies are installed.
2. Create output folder:
   - Linux/macOS: `mkdir -p docs/assets`
   - Windows (PowerShell): `New-Item -ItemType Directory -Force docs\\assets`
3. Build workflow object (`build_workflows(deps)`) in a local script/REPL.
4. Export graph image from the compiled workflow graph to:
   - `docs/assets/langgraph_flow.png`
5. If direct PNG export is unavailable, export Mermaid/text graph and convert manually, keeping the final filename above.
