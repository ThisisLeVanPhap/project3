package com.app.auth;

public record LoginResponse(
        boolean ok,
        String message,
        String tenantId,
        String tenantName
) {
    public static LoginResponse ok(String tenantId, String name, String code) {
        return new LoginResponse(true, "OK", tenantId, name);
    }

    public static LoginResponse fail(String msg) {
        return new LoginResponse(false, msg, null, null);
    }
}
