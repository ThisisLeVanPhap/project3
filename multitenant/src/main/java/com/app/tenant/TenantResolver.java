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

    @Override
    public boolean preHandle(HttpServletRequest req, HttpServletResponse res, Object handler) throws IOException {
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
