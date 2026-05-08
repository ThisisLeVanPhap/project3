# Agent Routing Guide

This file defines how to choose the right agent in the system.

## Default Routing Principle

Use the smallest effective routing strategy.

- If one domain clearly dominates, use one specialist.
- If many domains are involved, use orchestrator.
- If the task is about creating or improving agents, use teacher.
- If the task is simple, answer directly instead of over-routing.

## Primary Agents

### teacher
Use for:
- creating agents
- refining agents
- evaluating prompts, workflows, templates, and reusable references

### orchestrator
Use for:
- routing
- decomposition
- sequencing
- synthesis
- multi-domain coordination

### frontend-expert
Use for:
- UI architecture
- components
- state ownership
- accessibility
- responsiveness
- frontend reviews

### backend-expert
Use for:
- APIs
- validation
- service boundaries
- backend architecture
- backend reviews

### ai-product-engineer
Use for:
- AI feature design
- prompt workflows
- tool use
- application-level RAG decisions
- latency, cost, and reliability tradeoffs

### prompt-evals-expert
Use for:
- prompt review
- eval design
- output quality
- regression checks
- failure analysis

### rag-knowledge-expert
Use for:
- retrieval design
- chunking
- indexing
- grounding
- citation behavior
- freshness

### agent-systems-expert
Use for:
- multi-agent design
- delegation
- memory strategy
- orchestration patterns
- agent-system simplification

### devops-expert
Use for:
- CI/CD
- deploy workflows
- config and environments
- runtime reliability
- observability

### security-expert
Use for:
- auth/authz
- secrets
- trust boundaries
- misuse risks
- secure defaults

### qa-test-expert
Use for:
- test strategy
- regression planning
- release confidence
- risk-based validation

### llm-ops-expert
Use for:
- prompt/model/config versioning
- rollout and rollback
- latency/cost monitoring
- production LLM reliability

## Routing Anti-Patterns

Avoid:
- routing to many agents when one is enough
- routing to teacher for implementation tasks
- routing to orchestrator for trivial single-domain tasks
- routing to multiple agents with overlapping ownership and no synthesis plan