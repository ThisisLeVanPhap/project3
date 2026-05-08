# Testing Rules - chatbot service

## General rule
Every code change should be validated at the smallest useful scope.

## What to test

When changing retrieval:
- test normal retrieval
- test empty result case
- test tenant-scoped behavior if applicable
- test score/ranking behavior if changed
- for multilingual content, test both original-diacritic queries and accent-folded queries against the same sample KB

When changing API:
- test request validation
- test success response shape
- test at least one failure response

When changing KB pipeline:
- test chunk creation
- test metadata fields
- test malformed/empty input handling
- for curated scraping, keep `raw_urls.txt` as an explicit allowlist: one URL per line, optional `#` comments, no discovery/crawling, and include only the product/category/policy pages you want indexed

## Test style
- prefer small focused tests
- avoid brittle integration-heavy tests unless necessary
- test behavior, not internal implementation details

## Minimum validation before finishing a task
1. changed code runs
2. main path works
3. one edge case is covered
4. response schema remains compatible unless intentionally changed

## Suggested tools
- `pytest` for Python tests
- FastAPI test client where useful
- lightweight fixtures
