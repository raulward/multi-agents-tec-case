# Multi-Agent Financial QA (Template)

## Project Title
- Fill in the official project title here.

## Challenge Objective
- Briefly describe the technical challenge and expected outcome (2-4 lines).

## Quick Start (Local)
### Prerequisites
- Python version:
- Environment variables:
  - `OPENAI_API_KEY`
  - Other required vars from `app/core/config.py`

### Run
```bash
uvicorn app.main:app --reload
```

## API Endpoints
### `GET /v1/health`
- Purpose:
- Example response:

### `POST /v1/query`
- Purpose:
- Example request:
```json
{"query": "What is Apple gross margin?"}
```
- Example response (shape):
  - `final_answer`
  - `confidence`
  - `citations`
  - `trace`

### `POST /v1/ingest`
- Purpose:
- Example request:
```json
{"urls": ["https://example.com/report.pdf"]}
```

## Observability
- `run_id` per request
- `trace` with workflow steps
- token/cost accounting in trace/finalize step

## Known Limitations
- Fill current known gaps/limitations.

## Next Steps
- Fill short roadmap (3-5 bullets).
