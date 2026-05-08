package com.app.auth;

public record LoginResponse(
        boolean ok,
        String message,
        String userId,
        String role,
        String tenantId,
        String displayName,
        String email
) {
    public static LoginResponse ok(AppPrincipal principal) {
        return new LoginResponse(
                true,
                "OK",
                principal.userId(),
                principal.role().name(),
                principal.tenantId(),
                principal.displayName(),
                principal.email()
        );
    }

    public static LoginResponse fail(String msg) {
        return new LoginResponse(false, msg, null, null, null, null, null);
    }
}
