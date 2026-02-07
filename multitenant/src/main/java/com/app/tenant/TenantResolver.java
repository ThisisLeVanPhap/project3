package com.app.tenant;

import com.app.tenants.TenantRepository;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
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

        // ✅ Public endpoints (no tenant context yet)
        if (path.startsWith("/api/login")) return true;

        // ✅ UI routes (static pages)
        if (path.equals("/login") || path.startsWith("/login/")) return true;
        if (path.equals("/admin") || path.startsWith("/admin/")) return true;
        if (path.equals("/tenant") || path.startsWith("/tenant/")) return true;

        // ✅ Common static assets
        if (path.startsWith("/favicon")) return true;
        if (path.startsWith("/css/") || path.startsWith("/js/") || path.startsWith("/images/")) return true;

        // If your app serves static from /static/... or similar, you can add:
        // if (path.startsWith("/static/")) return true;

        return false;
    }

    @Override
    public boolean preHandle(HttpServletRequest req, HttpServletResponse res, Object handler) throws IOException {
        String path = req.getRequestURI();

        // ✅ BYPASS for login + static UIs
        if (shouldBypass(path)) {
            return true;
        }

        String tenantId = req.getHeader("X-Tenant-Id");
        String apiKey   = req.getHeader("X-API-Key");

        System.out.println("DBG TenantResolver -> X-API-Key=" + apiKey + ", X-Tenant-Id=" + tenantId);

        if (tenantId == null && apiKey != null && !apiKey.isBlank()) {
            var idOpt = tenantRepo.findIdByApiKey(apiKey);
            if (idOpt.isPresent()) tenantId = idOpt.get().toString();
            else {
                res.setStatus(401);
                res.getWriter().write("Invalid API key");
                return false;
            }
        }

        if (tenantId == null) {
            res.setStatus(400);
            res.getWriter().write("Missing tenant header (X-API-Key or X-Tenant-Id)");
            return false;
        }

        try { UUID.fromString(tenantId); }
        catch (IllegalArgumentException e) {
            res.setStatus(400);
            res.getWriter().write("Invalid tenant id format");
            return false;
        }

        TenantContext.set(tenantId);
        return true;
    }

    @Override
    public void afterCompletion(HttpServletRequest req, HttpServletResponse res, Object handler, Exception ex) {
        TenantContext.clear();
    }
}
