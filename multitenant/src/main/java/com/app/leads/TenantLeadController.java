package com.app.leads;

import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/tenant/api/leads")
public class TenantLeadController {

    private final LeadRepository leadRepo;

    public TenantLeadController(LeadRepository leadRepo) {
        this.leadRepo = leadRepo;
    }

    @GetMapping
    public List<Lead> list(@RequestParam("tid") String tenantId) {
        return leadRepo.findTop200ByTenantIdOrderByCreatedAtDesc(tenantId);
    }

    @PostMapping("/{id}/status")
    public Lead updateStatus(@PathVariable Long id,
                             @RequestParam("status") String status,
                             @RequestParam("tid") String tenantId) {

        Lead l = leadRepo.findById(id).orElseThrow();

        // ensure tenant isolation (even without auth)
        if (!tenantId.equals(l.getTenantId())) {
            throw new RuntimeException("Access denied");
        }

        l.setStatus(status);
        return leadRepo.save(l);
    }
}
