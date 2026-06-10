package com.app.purchases;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.math.BigDecimal;

public record ChatbotPurchaseRequestCreateRequest(
        @JsonProperty("handoff_id")
        String handoffId,
        @JsonProperty("idempotency_key")
        String idempotencyKey,
        @JsonProperty("tenant_id")
        String tenantId,
        @JsonProperty("conversation_id")
        String conversationId,
        String channel,
        @JsonProperty("customer_name")
        String customerName,
        String phone,
        String email,
        @JsonProperty("shipping_address")
        String shippingAddress,
        String notes,
        @JsonProperty("requested_product_ref")
        String requestedProductRef,
        @JsonProperty("product_sku")
        String productSku,
        @JsonProperty("product_url")
        String productUrl,
        BigDecimal price,
        Integer quantity
) {
}
