package com.app.purchases;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

public record PurchaseRequestResponse(
        Long id,
        @JsonProperty("tenant_id")
        String tenantId,
        String channel,
        @JsonProperty("conversation_id")
        String conversationId,
        @JsonProperty("lead_id")
        Long leadId,
        @JsonProperty("customer_name")
        String customerName,
        String phone,
        String email,
        @JsonProperty("shipping_address")
        String shippingAddress,
        String notes,
        @JsonProperty("requested_product_ref")
        String requestedProductRef,
        @JsonProperty("handoff_id")
        String handoffId,
        @JsonProperty("idempotency_key")
        String idempotencyKey,
        @JsonProperty("product_sku")
        String productSku,
        @JsonProperty("product_url")
        String productUrl,
        BigDecimal price,
        Integer quantity,
        String status,
        @JsonProperty("assigned_to_member_id")
        UUID assignedToMemberId,
        @JsonProperty("assigned_to_display_name")
        String assignedToDisplayName,
        @JsonProperty("claimed_at")
        Instant claimedAt,
        @JsonProperty("created_at")
        Instant createdAt,
        @JsonProperty("updated_at")
        Instant updatedAt
) {
    public static PurchaseRequestResponse from(PurchaseRequest purchaseRequest, String assignedToDisplayName) {
        return new PurchaseRequestResponse(
                purchaseRequest.getId(),
                purchaseRequest.getTenantId(),
                purchaseRequest.getChannel(),
                purchaseRequest.getConversationId(),
                purchaseRequest.getLeadId(),
                purchaseRequest.getCustomerName(),
                purchaseRequest.getPhone(),
                purchaseRequest.getEmail(),
                purchaseRequest.getShippingAddress(),
                purchaseRequest.getNotes(),
                purchaseRequest.getRequestedProductRef(),
                purchaseRequest.getHandoffId(),
                purchaseRequest.getIdempotencyKey(),
                purchaseRequest.getProductSku(),
                purchaseRequest.getProductUrl(),
                purchaseRequest.getPrice(),
                purchaseRequest.getQuantity(),
                purchaseRequest.getStatus(),
                purchaseRequest.getAssignedToMemberId(),
                assignedToDisplayName,
                purchaseRequest.getClaimedAt(),
                purchaseRequest.getCreatedAt(),
                purchaseRequest.getUpdatedAt()
        );
    }
}
