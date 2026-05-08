# Project Structure - chatbot service

## Goal
Keep the Python service modular enough for retrieval experiments and evaluation, but avoid over-engineering.

## Current important files
- `app/server.py`
- `app/retriever.py`
- `app/prompt.py`
- `app/state.py`
- `app/sales_flow.py`
- `app/guardrails.py`
- `tools/build_kb.py`
- `tools/scrape_site.py`

## Preferred direction
Move gradually toward:

```text
app/
  api/
  retrievers/
  rerankers/
  generation/
  kb/
  evaluation/
  core/
  state/
```

## Folder responsibilities

### `api/`
- FastAPI routes
- request/response models
- endpoint orchestration only

### `retrievers/`
- base retriever abstraction
- baseline retriever for current keyword search
- retrieval result schema / shared contracts
- tfidf retriever
- vector retriever
- hybrid retriever

Current boundary note:
- `retrieval_service` should be the single place that normalizes retriever outputs into the shared retrieval result schema
- endpoint code should prefer `retrieval_service` helpers over direct hit-shape assumptions

### `rerankers/`
- reranker interface
- candidate reranking implementations

### `generation/`
- prompt building
- answer generation
- citation formatting

### `kb/`
- document loaders
- text cleaning
- chunking
- metadata building
- indexing preparation

### `evaluation/`
- dataset loader
- validation
- metrics
- experiment runner

### `state/`
- keep chatbot state / sales flow logic here
- preserve existing behavior unless explicitly changing it

## Structure rules
- prefer adding modules over moving many old files at once
- avoid large cross-folder rewrites
- refactor one boundary at a time
- keep imports simple and local
