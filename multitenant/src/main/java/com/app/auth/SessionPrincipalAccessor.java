package com.app.auth;

import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ResponseStatusException;

import java.util.Arrays;

import static org.springframework.http.HttpStatus.FORBIDDEN;
import static org.springframework.http.HttpStatus.UNAUTHORIZED;

@Component
public class SessionPrincipalAccessor {

    public static final String SESSION_PRINCIPAL_KEY = "APP_PRINCIPAL";

    public AppPrincipal requireCurrent() {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication == null || !(authentication.getPrincipal() instanceof AppPrincipal principal)) {
            throw new ResponseStatusException(UNAUTHORIZED, "Authentication required");
        }
        return principal;
    }

    public String requireTenantId() {
        AppPrincipal principal = requireCurrent();
        if (principal.tenantId() == null || principal.tenantId().isBlank()) {
            throw new ResponseStatusException(UNAUTHORIZED, "Tenant-bound principal required");
        }
        return principal.tenantId();
    }

    public AppPrincipal requireAnyRole(AppRole... allowedRoles) {
        AppPrincipal principal = requireCurrent();
        boolean allowed = Arrays.stream(allowedRoles).anyMatch(role -> role == principal.role());
        if (!allowed) {
            throw new ResponseStatusException(FORBIDDEN, "Insufficient role");
        }
        return principal;
    }

    public AppPrincipal requirePlatformAdmin() {
        return requireAnyRole(AppRole.PLATFORM_ADMIN);
    }

    public AppPrincipal requireTenantAdmin() {
        return requireAnyRole(AppRole.TENANT_ADMIN);
    }

    public AppPrincipal requireTenantOperator() {
        return requireAnyRole(AppRole.TENANT_ADMIN, AppRole.TENANT_MEMBER);
    }

    public String requireTenantIdMatching(String requestedTenantId) {
        String currentTenantId = requireTenantId();
        if (requestedTenantId != null
                && !requestedTenantId.isBlank()
                && !currentTenantId.equals(requestedTenantId)) {
            throw new ResponseStatusException(FORBIDDEN, "Tenant scope mismatch");
        }
        return currentTenantId;
    }
}
