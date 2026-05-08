# Project Claude Memory

## Project Summary
- Project name: Multi-tenant AI sales assistant platform
- Product type: Graduation project / multi-service web system
- Main users:
  - platform admin
  - tenant admin
  - tenant member
  - end-user shopper
- Main product direction:
  - tenant-specific shopping assistant for furniture stores
  - extend toward general consumer assistant
  - extend toward lightweight market price reference / market insight support
- Primary goal for this phase:
  - make the product real enough that the graduation assignment sheet becomes true in implementation, not just in wording

## Stack
- Frontend: static admin/tenant pages, lightweight web UI
- Backend: Java 21, Spring Boot, Spring Security, Spring Data JPA
- AI: Python, FastAPI, Hugging Face Transformers, PEFT/LoRA
- Data: PostgreSQL, tenant-specific KB files, benchmark/eval artifacts
- Infrastructure: Docker, Docker Compose

## Working Style
- Reply in Vietnamese
- Be concise, practical, and repo-grounded
- Prefer minimal safe changes over rewrites
- Always inspect existing code before proposing changes
- Prefer shipping working product slices over writing abstract plans

## Core Delivery Rule
The objective is not to rewrite documentation.
The objective is to implement the missing product slices so that the graduation assignment sheet becomes as true as possible in the real repository.

When deciding between:
- prettier documentation
- more real product functionality

always prioritize more real product functionality.

## Project Conventions
- Do not redesign the whole architecture unless explicitly asked
- Preserve existing Spring Boot + FastAPI split
- Controllers stay thin; business logic goes into services
- Keep tenant isolation intact
- Prefer feature extension over framework replacement
- Do not claim a feature is complete if repo only shows prototype or partial implementation
- Extend existing modules first before inventing new parallel modules

## Product Truth Rules
For every requested feature, classify it as one of:
- already implemented
- partial / prototype
- missing but feasible extension

When implementing, prefer this order:
1. complete missing pieces of existing tenant-specific assistant
2. add general consumer assistant with maximum reuse of current architecture
3. add lightweight market price reference / market insight support with simple, explicit rules and demoable data
4. improve demoability, tests, startup flow, and operational visibility

## Routing Notes
- Use backend-expert for Spring Boot, RBAC, controllers, entities, purchase request, tenant logic
- Use ai-product-engineer for chatbot behavior, conversation flow, product strategy, prompt workflow
- Use rag-knowledge-expert for KB ingestion, retrieval mode, chunking, shortlist grounding, eval logic
- Use qa-test-expert for controller tests, retrieval benchmark validation, regression planning
- Use devops-expert for Docker Compose, service startup, deployment, observability
- Use frontend-expert only for admin/tenant UI or buyer-facing chat UI tasks
- Use teacher only to refine agents or CLAUDE instructions

## Important Constraints
- Do not break existing tenant-specific furniture chatbot flow
- Prefer realistic graduation-project scope over ambitious but unbuildable scope
- General consumer assistant and market insight must become real implementation if claimed
- Use repo evidence first, speculation second
- Keep backward compatibility for existing APIs where possible

## Architecture Notes
- Spring Boot is the system-of-record and business/API layer
- FastAPI is the AI/RAG/chat behavior layer
- Retrieval runtime currently leans on keyword baseline, while vector/hybrid exist and are benchmarked
- Messenger and Telegram integrations already exist
- Purchase request flow already exists and should remain usable
- Market insight is currently an extension target and should be implemented incrementally