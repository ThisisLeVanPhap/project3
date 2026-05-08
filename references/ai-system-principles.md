# AI System Principles

Use these principles when designing AI product features.

## General Rules

- Start with the simplest viable design.
- Do not assume RAG is needed.
- Do not assume multi-agent is needed.
- Do not assume tools are needed.
- Treat latency, cost, and reliability as first-class concerns.
- Prefer eval-backed iteration over intuition-only changes.

## Escalation Path

Prefer this order:
1. prompt-only
2. prompt + structured output
3. prompt + tool use
4. retrieval
5. multi-step workflow
6. multi-agent system

Only add complexity when simpler designs fail for clear reasons.

## Quality Rules

- Define the task clearly.
- Define success and failure explicitly.
- Identify likely failure modes.
- Define how the system will be evaluated.
- Keep the system debuggable.

## Operational Rules

- Version important prompts and configs.
- Watch latency and cost growth.
- Design fallback behavior.
- Avoid hidden dependencies.