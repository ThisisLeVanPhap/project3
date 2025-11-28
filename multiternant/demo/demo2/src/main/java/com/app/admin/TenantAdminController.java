package com.app.admin;

import com.app.tenants.Tenant;
import com.app.tenants.TenantRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/admin/tenants")
@RequiredArgsConstructor
public class TenantAdminController {
    private final TenantRepository repo;

    @PostMapping
    public Map<String, Object> create(@RequestBody Map<String, String> req) {
        Tenant t = new Tenant();
        t.setId(UUID.randomUUID());
        t.setCode(req.get("code"));
        t.setName(req.get("name"));
        t.setStatus("ACTIVE");
        t.setApiKey(UUID.randomUUID().toString().replace("-", ""));
        repo.save(t);
        return Map.of("tenantId", t.getId(), "apiKey", t.getApiKey());
    }
}
