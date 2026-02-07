package com.app.leads;

import com.app.leads.channel.MessengerOutbox;
import com.app.leads.channel.TelegramOutbox;
import com.app.leads.dto.ReplyReq;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/tenant/api/reply")
public class ReplyController {

    private final LeadRepository leadRepo;
    private final MessengerOutbox messengerOutbox;
    private final TelegramOutbox telegramOutbox;

    public ReplyController(LeadRepository leadRepo,
                           MessengerOutbox messengerOutbox,
                           TelegramOutbox telegramOutbox) {
        this.leadRepo = leadRepo;
        this.messengerOutbox = messengerOutbox;
        this.telegramOutbox = telegramOutbox;
    }

    @PostMapping
    public void reply(@RequestBody ReplyReq req,
                      @RequestParam("tid") String tenantId) {

        Lead lead = leadRepo.findById(req.leadId()).orElseThrow();

        // ✅ tenant isolation even without auth
        if (!tenantId.equals(lead.getTenantId())) {
            throw new RuntimeException("Access denied");
        }

        String msg = req.message() == null ? "" : req.message().trim();
        if (msg.isBlank()) return;

        if ("messenger".equalsIgnoreCase(lead.getChannel())) {
            messengerOutbox.sendText(tenantId, lead.getCustomerHandle(), msg);
        } else if ("telegram".equalsIgnoreCase(lead.getChannel())) {
            telegramOutbox.sendText(tenantId, lead.getCustomerHandle(), msg);
        } else {
            throw new RuntimeException("Unsupported channel: " + lead.getChannel());
        }
    }
}
