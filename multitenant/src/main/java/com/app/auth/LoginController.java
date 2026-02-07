package com.app.auth;

import com.app.tenants.Tenant;
import com.app.tenants.TenantRepository;
import org.springframework.web.bind.annotation.*;

import java.util.Optional;

@RestController
@RequestMapping("/api/login")
public class LoginController {

    private final TenantRepository tenantRepo;

    public LoginController(TenantRepository tenantRepo) {
        this.tenantRepo = tenantRepo;
    }

    @PostMapping("/tenant")
    public LoginResponse tenantLogin(@RequestBody LoginRequest req) {
        Optional<Tenant> t = tenantRepo.findByNameAndCode(
                req.name().trim(),
                req.code().trim()
        );

        if (t.isEmpty()) {
            return LoginResponse.fail("Invalid tenant name or code");
        }

        Tenant tenant = t.get();
        return LoginResponse.ok(
                String.valueOf(tenant.getId()),
                tenant.getName(),
                tenant.getCode()
        );
    }

    @PostMapping("/admin")
    public LoginResponse adminLogin(@RequestBody LoginRequest req) {
        if ("admin".equals(req.name()) && "admin123".equals(req.code())) {
            return LoginResponse.ok("admin", "admin", "admin");
        }
        return LoginResponse.fail("Invalid admin credentials");
    }
}
