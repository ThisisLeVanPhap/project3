# AGENTS.md

## Service identity
This directory contains the Python FastAPI AI service for the project.

Main responsibilities:
- retrieval
- knowledge base access
- optional reranking
- prompt orchestration
- answer generation
- evaluation utilities

This is part of an existing graduation project upgraded from Project 3.
It is NOT a greenfield rewrite.

## Project context
The full system has 2 main parts:
1. `chatbot/` = Python AI service
2. `multitenant/` = Spring Boot control plane

The Python service is the main refactor target.
The Spring Boot service should not be modified from this directory.

## Current architecture reality
Important existing files include:
- `app/server.py`
- `app/retriever.py`
- `app/prompt.py`
- `app/state.py`
- `app/sales_flow.py`
- `app/guardrails.py`
- `tools/build_kb.py`
- `tools/scrape_site.py`

Current reality:
- retrieval is still simple / baseline-oriented
- `server.py` currently mixes multiple responsibilities
- state / sales flow logic should be preserved unless the task explicitly requires changes

## Main development goals
Upgrade this service into a modular RAG-oriented service with:
- TF-IDF retrieval
- vector retrieval
- hybrid retrieval
- optional reranking
- answer generation with citations
- evaluation support
- tenant-aware request handling

## Hard constraints
- Do NOT rewrite the whole service
- Do NOT modify Spring Boot code from here
- Do NOT redesign unrelated chatbot business flow
- Do NOT rename files, classes, or modules without strong reason
- Prefer incremental refactor over clean-slate redesign
- Keep code simple and mergeable

## Coding principles
- readable code over clever code
- small, localized changes
- preserve existing behavior unless task says otherwise
- isolate retrieval / generation / API concerns
- use stable interfaces
- basic error handling is required
- avoid unnecessary dependencies

## Expected modular direction
Target modules should move toward:
- `retrievers/`
- `rerankers/`
- `generation/`
- `kb/`
- `evaluation/`
- `api/`

Do not force the whole structure in one task.
Create only the parts needed for the current task.

## Retrieval contract
Retriever outputs should converge toward a unified shape like:
- `doc_id`
- `chunk_id`
- `text`
- `title`
- `source`
- `score`
- `tenant_id`
- `metadata`

## API contract awareness
Before changing request/response models, check:
- `docs/api-contract.md`

Do not change endpoint payload shape casually.
If a contract change is necessary:
1. update the contract doc
2. mention compatibility risk
3. keep transition impact small

## Testing expectations
Before finishing a task:
- run focused tests for changed code
- if no test exists, add small local tests where practical
- validate main happy path
- validate at least one failure or empty-data case

See:
- `docs/testing.md`

## Task execution style
For each task:
1. inspect the relevant existing files first
2. propose the smallest useful change
3. implement only the requested scope
4. explain integration impact briefly
5. avoid touching unrelated modules

## Typical allowed tasks
- refactor retriever abstraction
- implement vector retriever
- implement hybrid retriever
- add reranker component
- improve FastAPI request/response models
- build evaluation loader/runner
- improve KB pipeline

## Typical disallowed behavior
- broad repo-wide cleanup
- changing many names for style only
- adding large frameworks without need
- editing multitenant Java code from this service
- changing sales flow logic without explicit task request
