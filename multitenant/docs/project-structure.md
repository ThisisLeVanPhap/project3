# Project Structure - multitenant service

## Goal
Preserve the existing Spring Boot architecture while making the chatbot integration cleaner and safer.

## Important areas
- tenant context / resolver
- tenant-scoped entities / listeners
- chat flow
- leads flow
- bots flow
- Python chatbot integration client

## Preferred change boundaries
Safe places to change:
- integration DTOs
- Python client layer
- controller/service mapping near chatbot calls
- timeout / fallback handling
- focused validation

Avoid unnecessary changes to:
- tenant core infrastructure
- unrelated repositories / entities
- existing business flows not part of the current task

## Structure rules
- controllers stay thin
- business logic stays in services
- integration-specific mapping stays near the integration layer
- avoid large package moves
- avoid broad renaming
