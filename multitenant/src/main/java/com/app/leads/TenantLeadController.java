package com.app.leads;

import com.app.auth.SessionPrincipalAccessor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/tenant/api/leads")
public class TenantLeadController {

    private final LeadRepository leadRepo;
    private final SessionPrincipalAccessor principalAccessor;

    public TenantLeadController(LeadRepository leadRepo, SessionPrincipalAccessor principalAccessor) {
        this.leadRepo = leadRepo;
        this.principalAccessor = principalAccessor;
    }

    @GetMapping
    public List<Lead> list(@RequestParam("tid") String tenantId) {
        principalAccessor.requireTenantOperator();
        return leadRepo.findTop200ByTenantIdOrderByCreatedAtDesc(
                principalAccessor.requireTenantIdMatching(tenantId)
        );
    }

    @PostMapping("/{id}/status")
    public Lead updateStatus(@PathVariable Long id,
                             @RequestParam("status") String status,
                             @RequestParam("tid") String tenantId) {
        principalAccessor.requireTenantOperator();
        String currentTenantId = principalAccessor.requireTenantIdMatching(tenantId);

        Lead l = leadRepo.findById(id).orElseThrow();
        if (!currentTenantId.equals(l.getTenantId())) {
            throw new RuntimeException("Access denied");
        }

        l.setStatus(status);
        return leadRepo.save(l);
    }
}
