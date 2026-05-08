package com.app.purchases;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.time.Instant;
import java.util.UUID;

public record PurchaseRequestResponse(
        Long id,
        @JsonProperty("customer_name")
        String customerName,
        String phone,
        @JsonProperty("shipping_address")
        String shippingAddress,
        String status,
        @JsonProperty("assigned_to_member_id")
        UUID assignedToMemberId,
        @JsonProperty("assigned_to_display_name")
        String assignedToDisplayName,
        @JsonProperty("claimed_at")
        Instant claimedAt,
        @JsonProperty("created_at")
        Instant createdAt
) {
    public static PurchaseRequestResponse from(PurchaseRequest purchaseRequest, String assignedToDisplayName) {
        return new PurchaseRequestResponse(
                purchaseRequest.getId(),
                purchaseRequest.getCustomerName(),
                purchaseRequest.getPhone(),
                purchaseRequest.getShippingAddress(),
                purchaseRequest.getStatus(),
                purchaseRequest.getAssignedToMemberId(),
                assignedToDisplayName,
                purchaseRequest.getClaimedAt(),
                purchaseRequest.getCreatedAt()
        );
    }
}
