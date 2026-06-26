package com.app.general;

public enum SourceVisibility {
    GLOBAL_PUBLIC,
    TENANT_BOUND,
    PRIVATE,
    ADMIN_ONLY;

    public static SourceVisibility fromString(String value) {
        if (value == null || value.isBlank()) return TENANT_BOUND;
        return switch (value.trim().toUpperCase()) {
            case "GLOBAL_PUBLIC" -> GLOBAL_PUBLIC;
            case "TENANT_BOUND" -> TENANT_BOUND;
            case "PRIVATE" -> PRIVATE;
            case "ADMIN_ONLY" -> ADMIN_ONLY;
            default -> TENANT_BOUND;
        };
    }

    public static boolean isValid(String value) {
        if (value == null || value.isBlank()) return false;
        return switch (value.trim().toUpperCase()) {
            case "GLOBAL_PUBLIC", "TENANT_BOUND", "PRIVATE", "ADMIN_ONLY" -> true;
            default -> false;
        };
    }
}
