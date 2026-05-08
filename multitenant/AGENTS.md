# AGENTS.md

## Service identity
This directory contains the Spring Boot multi-tenant control plane.

Main responsibilities:
- tenant management
- business logic
- routing
- integration with the Python chatbot service
- existing chat / leads / bots flows

This is part of an existing graduation project upgraded from Project 3.
It is NOT a greenfield rewrite.

## Project context
The full system has 2 main parts:
1. `multitenant/` = Spring Boot control plane
2. `chatbot/` = Python AI service

The Spring Boot side should remain mostly intact.
This service should not modify Python code from here.

## Current architecture reality
Important existing concepts/files include:
- tenant context and resolution
- tenant-scoped entities / listeners
- chat, leads, bots flows
- existing Python integration client
- legacy serving assumptions may still exist

Preserve existing tenant-aware architecture unless a task explicitly changes it.

## Main development goals
This service should support:
- passing `tenant_id` correctly to the Python chatbot service
- handling request/response integration cleanly
- preserving current business flows
- adding safe timeout/error handling
- staying compatible with evolving chatbot API contract

## Hard constraints
- Do NOT rewrite the whole Spring Boot service
- Do NOT redesign tenant architecture
- Do NOT modify Python files from here
- Do NOT rename unrelated classes or packages
- Prefer incremental changes that are easy to merge

## Coding principles
- preserve tenant-aware flow
- keep controllers thin
- keep service responsibilities clear
- prefer minimal changes near the integration boundary
- handle failures gracefully
- avoid unnecessary framework additions

## Integration awareness
Before changing chatbot-related request/response mapping, check:
- `docs/api-contract.md`

If the contract changes:
1. update this doc
2. mention compatibility risk
3. keep the transition small and explicit

## Testing expectations
Before finishing a task:
- test controller/service behavior for changed flow
- validate tenant propagation
- validate Python client failure handling
- validate response mapping when changed

See:
- `docs/testing.md`

## Typical allowed tasks
- update chatbot client DTOs
- adjust controller/service integration
- pass tenant-aware payloads
- improve timeout and error mapping
- add focused tests around Python integration

## Typical disallowed behavior
- broad package refactors
- redesigning unrelated business modules
- changing persistence model without need
- modifying Python service logic from this directory
