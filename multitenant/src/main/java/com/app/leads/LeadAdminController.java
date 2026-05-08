package com.app.leads;

import com.app.auth.SessionPrincipalAccessor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/admin/api/leads")
public class LeadAdminController {

    private final LeadRepository leadRepo;
    private final SessionPrincipalAccessor principalAccessor;

    public LeadAdminController(LeadRepository leadRepo, SessionPrincipalAccessor principalAccessor) {
        this.leadRepo = leadRepo;
        this.principalAccessor = principalAccessor;
    }

    @GetMapping
    public List<Lead> list(@RequestParam("tenantId") String tenantId) {
        principalAccessor.requirePlatformAdmin();
        return leadRepo.findTop200ByTenantIdOrderByCreatedAtDesc(tenantId);
    }

    @PostMapping("/{id}/status")
    public Lead updateStatus(
            @PathVariable Long id,
            @RequestParam("status") String status
    ) {
        principalAccessor.requirePlatformAdmin();
        Lead l = leadRepo.findById(id).orElseThrow();
        l.setStatus(status);
        return leadRepo.save(l);
    }
}
