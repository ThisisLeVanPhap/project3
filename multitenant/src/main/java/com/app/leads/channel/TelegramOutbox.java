package com.app.leads.channel;

import com.app.telegram.TelegramBotBindingRepository;
import com.app.telegram.TelegramSendService;
import org.springframework.stereotype.Service;

import java.util.UUID;

@Service
public class TelegramOutbox {

    private final TelegramSendService sendService;
    private final TelegramBotBindingRepository bindingRepo;

    public TelegramOutbox(TelegramSendService sendService, TelegramBotBindingRepository bindingRepo) {
        this.sendService = sendService;
        this.bindingRepo = bindingRepo;
    }

    public void sendText(String tenantId, String chatId, String text) {
        UUID tid;
        try {
            tid = UUID.fromString(tenantId);
        } catch (Exception e) {
            throw new RuntimeException("Invalid tenantId (expected UUID string): " + tenantId);
        }

        var bindings = bindingRepo.findAllByTenantId(tid);
        if (bindings == null || bindings.isEmpty()) {
            throw new RuntimeException("No Telegram bot binding for tenant");
        }

        // Pick any binding (first). If you want "ACTIVE" only, filter here.
        var binding = bindings.get(0);
        sendService.sendText(binding.getBotToken(), chatId, text);
    }
}
