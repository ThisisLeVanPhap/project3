package com.app.leads;

import com.app.auth.SessionPrincipalAccessor;
import com.app.leads.channel.MessengerOutbox;
import com.app.leads.channel.TelegramOutbox;
import com.app.leads.dto.OrderInfoReq;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/tenant/api/leads-ops")
public class LeadTenantOpsController {

    private final LeadRepository leadRepo;
    private final MessengerOutbox messengerOutbox;
    private final TelegramOutbox telegramOutbox;
    private final SessionPrincipalAccessor principalAccessor;

    public LeadTenantOpsController(LeadRepository leadRepo,
                                   MessengerOutbox messengerOutbox,
                                   TelegramOutbox telegramOutbox,
                                   SessionPrincipalAccessor principalAccessor) {
        this.leadRepo = leadRepo;
        this.messengerOutbox = messengerOutbox;
        this.telegramOutbox = telegramOutbox;
        this.principalAccessor = principalAccessor;
    }

    @PostMapping("/order-info")
    public Lead saveOrderInfo(@RequestBody OrderInfoReq req,
                              @RequestParam("tid") String tenantId) {
        principalAccessor.requireTenantOperator();
        String currentTenantId = principalAccessor.requireTenantIdMatching(tenantId);

        Lead lead = requireLead(req.leadId(), currentTenantId);

        lead.setOrderInfo(req.orderInfo() == null ? "" : req.orderInfo().trim());
        lead.setShippingStatus("READY");
        return leadRepo.save(lead);
    }

    @PostMapping("/{id}/ship")
    public Lead markShipped(@PathVariable Long id,
                            @RequestParam("tid") String tenantId) {
        principalAccessor.requireTenantOperator();
        String currentTenantId = principalAccessor.requireTenantIdMatching(tenantId);

        Lead lead = requireLead(id, currentTenantId);

        lead.setShippingStatus("SHIPPED");
        leadRepo.save(lead);

        String notify = "Your order has been shipped. If you need anything else, just reply here.";

        if ("messenger".equalsIgnoreCase(lead.getChannel())) {
            messengerOutbox.sendText(currentTenantId, lead.getCustomerHandle(), notify);
        } else if ("telegram".equalsIgnoreCase(lead.getChannel())) {
            telegramOutbox.sendText(currentTenantId, lead.getCustomerHandle(), notify);
        }

        lead.setStage("FULFILLED");
        return leadRepo.save(lead);
    }

    @PostMapping("/{id}/reset")
    public Lead resetConversation(@PathVariable Long id,
                                  @RequestParam("tid") String tenantId) {
        principalAccessor.requireTenantOperator();
        String currentTenantId = principalAccessor.requireTenantIdMatching(tenantId);

        Lead lead = requireLead(id, currentTenantId);

        lead.setStage("DISCOVER");
        leadRepo.save(lead);

        return lead;
    }

    private Lead requireLead(Long id, String tenantId) {
        return leadRepo.findByIdAndTenantId(id, tenantId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Lead not found"));
    }
}
