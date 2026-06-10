package com.app.purchases;

public record PurchaseRequestUpdateRequest(
        String customerName,
        String phone,
        String shippingAddress,
        String notes,
        String requestedProductRef
) {}
