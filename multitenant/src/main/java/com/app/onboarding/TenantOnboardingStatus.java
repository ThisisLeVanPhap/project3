package com.app.onboarding;

import java.util.Locale;

public enum TenantOnboardingStatus {
    NEW,
    CONTACTED,
    APPROVED,
    REJECTED,
    PROVISIONED;

    static TenantOnboardingStatus parse(String value) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException("status is required");
        }
        try {
            return TenantOnboardingStatus.valueOf(value.trim().toUpperCase(Locale.ROOT));
        } catch (IllegalArgumentException ex) {
            throw new IllegalArgumentException("Unsupported onboarding status: " + value);
        }
    }
}
