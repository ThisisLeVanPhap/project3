package com.app.purchases;

import com.fasterxml.jackson.annotation.JsonProperty;

public record ChatbotPurchaseRequestCreateResponse(
        Long id,
        @JsonProperty("handoff_id")
        String handoffId,
        @JsonProperty("idempotency_key")
        String idempotencyKey,
        String status,
        boolean created,
        @JsonProperty("purchase_request")
        PurchaseRequestResponse purchaseRequest
) {
    public static ChatbotPurchaseRequestCreateResponse from(PurchaseRequestService.ChatbotCreateResult result) {
        PurchaseRequest purchaseRequest = result.purchaseRequest();
        return new ChatbotPurchaseRequestCreateResponse(
                purchaseRequest.getId(),
                purchaseRequest.getHandoffId(),
                purchaseRequest.getIdempotencyKey(),
                purchaseRequest.getStatus(),
                result.created(),
                PurchaseRequestResponse.from(purchaseRequest, null)
        );
    }
}
