package com.app.leads;

import com.app.leads.channel.MessengerOutbox;
import com.app.leads.channel.TelegramOutbox;
import com.app.leads.dto.OrderInfoReq;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/tenant/api/leads-ops")
public class LeadTenantOpsController {

    private final LeadRepository leadRepo;
    private final MessengerOutbox messengerOutbox;
    private final TelegramOutbox telegramOutbox;

    public LeadTenantOpsController(LeadRepository leadRepo,
                                   MessengerOutbox messengerOutbox,
                                   TelegramOutbox telegramOutbox) {
        this.leadRepo = leadRepo;
        this.messengerOutbox = messengerOutbox;
        this.telegramOutbox = telegramOutbox;
    }

    @PostMapping("/order-info")
    public Lead saveOrderInfo(@RequestBody OrderInfoReq req,
                              @RequestParam("tid") String tenantId) {

        Lead lead = leadRepo.findById(req.leadId()).orElseThrow();
        if (!tenantId.equals(lead.getTenantId())) throw new RuntimeException("Access denied");

        lead.setOrderInfo(req.orderInfo() == null ? "" : req.orderInfo().trim());
        lead.setShippingStatus("READY");
        return leadRepo.save(lead);
    }

    @PostMapping("/{id}/ship")
    public Lead markShipped(@PathVariable Long id,
                            @RequestParam("tid") String tenantId) {

        Lead lead = leadRepo.findById(id).orElseThrow();
        if (!tenantId.equals(lead.getTenantId())) throw new RuntimeException("Access denied");

        lead.setShippingStatus("SHIPPED");
        leadRepo.save(lead);

        // ✅ auto notify customer
        String notify = "✅ Your order has been shipped. If you need anything else, just reply here.";

        if ("messenger".equalsIgnoreCase(lead.getChannel())) {
            messengerOutbox.sendText(tenantId, lead.getCustomerHandle(), notify);
        } else if ("telegram".equalsIgnoreCase(lead.getChannel())) {
            telegramOutbox.sendText(tenantId, lead.getCustomerHandle(), notify);
        }

        return lead;
    }
}
