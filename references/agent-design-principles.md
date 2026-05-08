# Agent Design Principles

This file defines the default design principles for specialist agents in this repository.

## Goals

Agents in this system should be:
- practical
- reusable
- maintainable
- easy to route correctly
- easy to refine per project

## Good Agent Characteristics

A good agent should have:
- a clear purpose
- a clear "when to use" description
- explicit scope
- explicit non-scope
- a short workflow
- decision rules
- a review or quality checklist
- a structured output format

## Bad Agent Patterns

Avoid:
- vague roles
- overlapping responsibilities
- giant theory dumps
- project-specific assumptions in master agents
- hardcoded framework choices unless the agent is explicitly framework-specific
- prompts that try to solve every possible use case

## Reusability Rules

Master agents should:
- stay framework-agnostic by default
- capture stable engineering judgment
- leave project-specific details to CLAUDE.md and project references
- be easy to clone across projects

## Refinement Rules

When adapting an agent for a real project:
1. change project CLAUDE.md first
2. add project references next
3. refine the agent only if project-specific behavior is strong enough to justify it

Do not fork agents too early.