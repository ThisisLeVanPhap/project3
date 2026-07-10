package com.app.purchases;

import java.util.Locale;

public enum PurchaseRequestStatus {
    NEW,
    PROCESSING,
    COMPLETED,
    RESET_DISCARDED;

    public static boolean isInProgress(String rawStatus) {
        String status = normalize(rawStatus);
        return NEW.name().equals(status) || PROCESSING.name().equals(status);
    }

    public static boolean isFinal(String rawStatus) {
        return !isInProgress(rawStatus);
    }

    public static String normalize(String rawStatus) {
        if (rawStatus == null || rawStatus.isBlank()) {
            throw new IllegalArgumentException("Status is required");
        }
        String normalizedRaw = rawStatus.trim().toUpperCase(Locale.ROOT);
        if ("CONTACTED".equals(normalizedRaw)) {
            return PROCESSING.name();
        }
        try {
            return PurchaseRequestStatus.valueOf(normalizedRaw).name();
        } catch (IllegalArgumentException ex) {
            throw new IllegalArgumentException("Unsupported purchase request status: " + rawStatus);
        }
    }
}
