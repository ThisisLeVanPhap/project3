package com.app.leads;

import com.fasterxml.jackson.annotation.JsonProperty;

public record ChatbotLeadCreateResponse(
        Long id,
        @JsonProperty("handoff_id")
        String handoffId,
        @JsonProperty("idempotency_key")
        String idempotencyKey,
        String status,
        String stage,
        boolean created,
        Lead lead
) {
}
