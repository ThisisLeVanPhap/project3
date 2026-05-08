# API Contract - chatbot service

## Purpose

This document defines the payload contract between the Spring Boot
service and the Python chatbot service.

Any change here must be treated as an integration change.

------------------------------------------------------------------------

## Main endpoint

### POST /chat

This endpoint accepts a tenant-aware chat request and returns an answer
with citations.

## Request body

``` json
{
  "tenant_id": "tenant-001",
  "query": "What is your return policy?",
  "retrieval_mode": "hybrid",
  "top_k": 5
}
```

## Request fields

-   `tenant_id`: required string
-   `query`: required string
-   `retrieval_mode`: optional string\
    allowed values:
    -   tfidf
    -   vector
    -   hybrid
    -   hybrid_rerank
-   `top_k`: optional integer\
    default: 5

## Response body

``` json
{
  "answer": "You can return items within 7 days if they are unused.",
  "citations": [
    {
      "doc_id": "return-policy",
      "chunk_id": "return-policy-01",
      "title": "Return Policy",
      "source": "kb/return-policy.md",
      "score": 0.91
    }
  ],
  "retrieval_mode": "hybrid",
  "tenant_id": "tenant-001"
}
```

## Response fields

-   `answer`: generated answer text
-   `citations`: list of supporting chunks
-   `retrieval_mode`: actual retrieval mode used
-   `tenant_id`: tenant used for lookup

## Citation rules

-   citations should come from retrieved chunks
-   citations should be empty only when no evidence is available
-   do not fabricate citation metadata

## Unified retrieval result schema

Retriever outputs should normalize to this internal shape before they are
used for context building, citation formatting, or reranking:

-   `doc_id`
-   `chunk_id`
-   `text`
-   `title`
-   `source`
-   `score`
-   `tenant_id`
-   `metadata`

Compatibility note:

-   this standardizes the internal retrieval result format used by the
    Python service
-   `/chat` endpoint behavior is unchanged in this task
-   response payload changes should remain additive and coordinated with
    Spring integration

------------------------------------------------------------------------

## Error cases

### 400 Bad Request

``` json
{
  "error": "invalid_request",
  "message": "tenant_id and query are required"
}
```

### 404 Not Found

``` json
{
  "error": "tenant_kb_not_found",
  "message": "Knowledge base not found for tenant"
}
```

### 422 Unprocessable Entity

Use when: - retrieval mode is invalid - field values fail validation

### 500 Internal Server Error

``` json
{
  "error": "internal_error",
  "message": "Unexpected server error"
}
```

------------------------------------------------------------------------

## Contract rules

-   do not rename fields casually
-   do not remove fields without coordination
-   additive changes are preferred over breaking changes
-   Spring integration must be updated if request/response structure
    changes
