package com.app.auth;

import java.io.Serializable;

public record AppPrincipal(
        String userId,
        AppRole role,
        String tenantId,
        String displayName,
        String email
) implements Serializable {}
