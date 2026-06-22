package com.app.chat;

import com.app.auth.AppPrincipal;
import com.app.auth.AppRole;
import com.app.auth.SessionPrincipalAccessor;
import com.app.tenant.TenantContext;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.util.UUID;

@RestController
@RequestMapping("/api/admin/conversations")
@RequiredArgsConstructor
public class ConversationResetController {

    private final ConversationResetService resetService;
    private final SessionPrincipalAccessor principalAccessor;

    @PostMapping("/reset")
    public ConversationResetResponse reset(@RequestBody ConversationResetRequest request) {
        AppPrincipal principal = principalAccessor.requireAnyRole(AppRole.PLATFORM_ADMIN, AppRole.TENANT_ADMIN);
        UUID tenantId = resolveTenantId(principal);
        return resetService.reset(tenantId, request);
    }

    private UUID resolveTenantId(AppPrincipal principal) {
        String tenantId = principal.role() == AppRole.PLATFORM_ADMIN
                ? TenantContext.get()
                : principal.tenantId();
        if (tenantId == null || tenantId.isBlank()) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "Tenant context required. Select a tenant or send X-Tenant-Id/X-API-Key."
            );
        }
        try {
            return UUID.fromString(tenantId);
        } catch (IllegalArgumentException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Invalid tenant id format");
        }
    }
}
