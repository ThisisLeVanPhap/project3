package com.app.leads;

import com.app.auth.SessionPrincipalAccessor;
import com.app.leads.channel.MessengerOutbox;
import com.app.leads.channel.TelegramOutbox;
import com.app.leads.dto.ReplyReq;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/tenant/api/reply")
public class ReplyController {

    private final LeadRepository leadRepo;
    private final MessengerOutbox messengerOutbox;
    private final TelegramOutbox telegramOutbox;
    private final SessionPrincipalAccessor principalAccessor;

    public ReplyController(LeadRepository leadRepo,
                           MessengerOutbox messengerOutbox,
                           TelegramOutbox telegramOutbox,
                           SessionPrincipalAccessor principalAccessor) {
        this.leadRepo = leadRepo;
        this.messengerOutbox = messengerOutbox;
        this.telegramOutbox = telegramOutbox;
        this.principalAccessor = principalAccessor;
    }

    @PostMapping
    public void reply(@RequestBody ReplyReq req,
                      @RequestParam("tid") String tenantId) {
        principalAccessor.requireTenantOperator();
        String currentTenantId = principalAccessor.requireTenantIdMatching(tenantId);

        Lead lead = leadRepo.findByIdAndTenantId(req.leadId(), currentTenantId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Lead not found"));

        String msg = req.message() == null ? "" : req.message().trim();
        if (msg.isBlank()) return;

        if ("messenger".equalsIgnoreCase(lead.getChannel())) {
            messengerOutbox.sendText(currentTenantId, lead.getCustomerHandle(), msg);
        } else if ("telegram".equalsIgnoreCase(lead.getChannel())) {
            telegramOutbox.sendText(currentTenantId, lead.getCustomerHandle(), msg);
        } else {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Unsupported channel: " + lead.getChannel());
        }
    }
}
