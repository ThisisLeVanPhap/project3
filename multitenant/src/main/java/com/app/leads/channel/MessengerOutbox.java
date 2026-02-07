package com.app.leads.channel;

import com.app.messenger.MessengerPageBindingRepository;
import com.app.messenger.MessengerSendService;
import org.springframework.stereotype.Service;

import java.util.UUID;

@Service
public class MessengerOutbox {

    private final MessengerSendService sendService;
    private final MessengerPageBindingRepository pageBindingRepo;

    public MessengerOutbox(MessengerSendService sendService, MessengerPageBindingRepository pageBindingRepo) {
        this.sendService = sendService;
        this.pageBindingRepo = pageBindingRepo;
    }

    public void sendText(String tenantId, String psid, String text) {
        UUID tid;
        try {
            tid = UUID.fromString(tenantId);
        } catch (Exception e) {
            throw new RuntimeException("Invalid tenantId (expected UUID string): " + tenantId);
        }

        var bindings = pageBindingRepo.findAllByTenantId(tid);
        if (bindings == null || bindings.isEmpty()) {
            throw new RuntimeException("No Messenger page binding for tenant");
        }

        // Pick any binding (first). If you want "ACTIVE" only, filter here.
        var binding = bindings.get(0);
        sendService.sendText(psid, text, binding.getPageAccessToken());
    }
}
