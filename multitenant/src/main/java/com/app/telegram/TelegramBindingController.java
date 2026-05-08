package com.app.telegram;

import com.app.auth.SessionPrincipalAccessor;
import com.app.bots.ChatbotInstance;
import com.app.bots.ChatbotInstanceRepository;
import com.app.telegram.dto.CreateTelegramBindingDto;
import com.app.tenant.TenantContext;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.security.SecureRandom;
import java.util.Base64;
import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/telegram/bindings")
@RequiredArgsConstructor
public class TelegramBindingController {

    private final TelegramBotBindingRepository bindingRepo;
    private final ChatbotInstanceRepository botRepo;
    private final SessionPrincipalAccessor principalAccessor;

    @GetMapping
    public List<TelegramBotBinding> listMine() {
        principalAccessor.requireTenantAdmin();
        UUID tenantId = UUID.fromString(TenantContext.get());
        return bindingRepo.findAllByTenantId(tenantId);
    }

    @PostMapping
    public TelegramBotBinding create(@RequestBody CreateTelegramBindingDto dto) {
        principalAccessor.requireTenantAdmin();
        UUID tenantId = UUID.fromString(TenantContext.get());

        ChatbotInstance bot = botRepo.findById(dto.chatbotId())
                .orElseThrow(() -> new IllegalArgumentException("Chatbot not found"));

        if (!bot.getTenantId().equals(tenantId)) {
            throw new IllegalArgumentException("Chatbot does not belong to this tenant");
        }

        bindingRepo.findByTenantIdAndChatbotId(tenantId, dto.chatbotId())
                .ifPresent(x -> { throw new IllegalArgumentException("This chatbot is already bound to Telegram"); });

        TelegramBotBinding b = new TelegramBotBinding();
        b.setId(UUID.randomUUID());
        b.setTenantId(tenantId);
        b.setChatbotId(dto.chatbotId());
        b.setBotToken(dto.botToken());
        b.setSecretPath(randomSecretPath());
        b.setStatus("ACTIVE");

        return bindingRepo.save(b);
    }

    private String randomSecretPath() {
        byte[] buf = new byte[32];
        new SecureRandom().nextBytes(buf);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(buf);
    }
}
