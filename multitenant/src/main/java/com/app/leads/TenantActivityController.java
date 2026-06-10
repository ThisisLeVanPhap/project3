package com.app.leads;

import com.app.auth.SessionPrincipalAccessor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/tenant/api")
public class TenantActivityController {

    private final LeadRepository leadRepo;
    private final SessionPrincipalAccessor principalAccessor;

    public TenantActivityController(LeadRepository leadRepo, SessionPrincipalAccessor principalAccessor) {
        this.leadRepo = leadRepo;
        this.principalAccessor = principalAccessor;
    }

    @GetMapping("/activity")
    public List<LeadActivityDto> getRecentActivity(
            @RequestParam(value = "limit", defaultValue = "10") int limit
    ) {
        principalAccessor.requireTenantOperator();
        String tenantId = principalAccessor.requireTenantId();

        List<Lead> recentLeads = leadRepo.findTop10ByTenantIdOrderByCreatedAtDesc(tenantId);

        return recentLeads.stream()
                .map(lead -> new LeadActivityDto(
                        "lead_created",
                        "New lead from " + lead.getCustomerHandle(),
                        lead.getCreatedAt(),
                        "Channel: " + lead.getChannel()
                ))
                .toList();
    }
}
