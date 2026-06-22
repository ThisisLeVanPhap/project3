package com.app.purchases;

import java.util.Locale;

public enum PurchaseRequestStatus {
    NEW,
    CONTACTED,
    COMPLETED,
    RESET_DISCARDED;

    public static boolean isInProgress(String rawStatus) {
        String status = normalize(rawStatus);
        return NEW.name().equals(status) || CONTACTED.name().equals(status);
    }

    public static boolean isFinal(String rawStatus) {
        return !isInProgress(rawStatus);
    }

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
