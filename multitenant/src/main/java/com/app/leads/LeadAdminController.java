package com.app.leads;

import org.springframework.web.bind.annotation.*;
import java.util.List;

@RestController
@RequestMapping("/admin/api/leads")
public class LeadAdminController {

    private final LeadRepository leadRepo;

    public LeadAdminController(LeadRepository leadRepo) {
        this.leadRepo = leadRepo;
    }

    // Platform admin: chọn tenant nào cũng được
    @GetMapping
    public List<Lead> list(@RequestParam("tenantId") String tenantId) {
        return leadRepo.findTop200ByTenantIdOrderByCreatedAtDesc(tenantId);
    }

    @PostMapping("/{id}/status")
    public Lead updateStatus(
            @PathVariable Long id,
            @RequestParam("status") String status
    ) {
        Lead l = leadRepo.findById(id).orElseThrow();
        l.setStatus(status);
        return leadRepo.save(l);
    }
}
