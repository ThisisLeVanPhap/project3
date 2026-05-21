package com.app.tenant;

import com.app.auth.AppPrincipal;
import com.app.auth.AppRole;
import com.app.auth.SessionPrincipalAccessor;
import com.app.tenants.TenantRepository;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

import java.io.IOException;
import java.util.UUID;

@Component
@RequiredArgsConstructor
public class TenantResolver implements HandlerInterceptor {
    private final TenantRepository tenantRepo;

    private boolean shouldBypass(String path) {
        if (path == null) return false;

        if (path.startsWith("/api/login")) return true;
        if (path.equals("/api/onboarding-requests") || path.startsWith("/api/onboarding-requests/")) return true;
        if (path.equals("/api/me")) return true;

        if (path.equals("/login") || path.startsWith("/login/")) return true;
        if (path.equals("/admin") || path.startsWith("/admin/")) return true;
        if (path.equals("/tenant") || path.startsWith("/tenant/")) return true;

        if (path.startsWith("/favicon")) return true;
        if (path.startsWith("/css/") || path.startsWith("/js/") || path.startsWith("/images/")) return true;

        if (path.startsWith("/api/general/")) return true;

        return false;
    }

    @Override
    public boolean preHandle(HttpServletRequest req, HttpServletResponse res, Object handler) throws IOException {
        String path = req.getRequestURI();
        if (shouldBypass(path)) {
            return true;
        }

        HttpSession session = req.getSession(false);
        if (session != null) {
            Object value = session.getAttribute(SessionPrincipalAccessor.SESSION_PRINCIPAL_KEY);
            if (value instanceof AppPrincipal principal) {
                if (principal.role() == AppRole.PLATFORM_ADMIN) {
                    if (hasTenantScopeHeader(req)) {
                        String requestedTenantId = resolveTenantIdFromHeaders(req, res, true);
                        if (requestedTenantId == null) {
                            return false;
                        }
                        TenantContext.set(requestedTenantId);
                    }
                    return true;
                }

                if (principal.tenantId() != null && !principal.tenantId().isBlank()) {
                    TenantContext.set(principal.tenantId());
                }
                return true;
            }
        }

        String tenantId = resolveTenantIdFromHeaders(req, res, true);
        if (tenantId == null) {
            return false;
        }

        TenantContext.set(tenantId);
        return true;
    }

    private String resolveTenantIdFromHeaders(
            HttpServletRequest req,
            HttpServletResponse res,
            boolean required
    ) throws IOException {
        String tenantId = req.getHeader("X-Tenant-Id");
        String apiKey = req.getHeader("X-API-Key");

        if ((tenantId == null || tenantId.isBlank()) && apiKey != null && !apiKey.isBlank()) {
            var idOpt = tenantRepo.findIdByApiKey(apiKey);
            if (idOpt.isPresent()) {
                tenantId = idOpt.get().toString();
            } else {
                res.setStatus(401);
                res.getWriter().write("Invalid API key");
                return null;
            }
        }

        if (tenantId == null || tenantId.isBlank()) {
            if (required) {
                res.setStatus(400);
                res.getWriter().write("Missing tenant header (X-API-Key or X-Tenant-Id)");
            }
            return null;
        }

        try {
            UUID.fromString(tenantId);
        } catch (IllegalArgumentException e) {
            res.setStatus(400);
            res.getWriter().write("Invalid tenant id format");
            return null;
        }

        return tenantId;
    }

    private boolean hasTenantScopeHeader(HttpServletRequest req) {
        String tenantId = req.getHeader("X-Tenant-Id");
        String apiKey = req.getHeader("X-API-Key");
        return (tenantId != null && !tenantId.isBlank()) || (apiKey != null && !apiKey.isBlank());
    }

    @Override
    public void afterCompletion(HttpServletRequest req, HttpServletResponse res, Object handler, Exception ex) {
        TenantContext.clear();
    }
}
