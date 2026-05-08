package com.app.auth;

public enum AppRole {
    PLATFORM_ADMIN,
    TENANT_ADMIN,
    TENANT_MEMBER;

    public static AppRole fromDbValue(String value) {
        return AppRole.valueOf(value == null ? "" : value.trim().toUpperCase());
    }
}
