package com.app.purchases;

import java.util.Locale;

public enum PurchaseRequestStatus {
    NEW,
    CONTACTED,
    COMPLETED;

    public static String normalize(String rawStatus) {
        if (rawStatus == null || rawStatus.isBlank()) {
            throw new IllegalArgumentException("Status is required");
        }
        try {
            return PurchaseRequestStatus.valueOf(rawStatus.trim().toUpperCase(Locale.ROOT)).name();
        } catch (IllegalArgumentException ex) {
            throw new IllegalArgumentException("Unsupported purchase request status: " + rawStatus);
        }
    }
}
