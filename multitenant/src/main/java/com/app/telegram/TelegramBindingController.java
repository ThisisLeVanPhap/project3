package com.app.telegram;

import com.app.auth.AppPrincipal;
import com.app.auth.AppRole;
import com.app.auth.SessionPrincipalAccessor;
import com.app.bots.ChatbotInstance;
import com.app.bots.ChatbotInstanceRepository;
import com.app.telegram.dto.CreateTelegramBindingDto;
import com.app.tenant.TenantContext;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

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
    private final TelegramSendService sendService;

    private static final org.slf4j.Logger log = org.slf4j.LoggerFactory.getLogger(TelegramBindingController.class);

    @GetMapping
    public List<TelegramBotBinding> listMine() {
        UUID tenantId = requireBindingTenantId();
        return bindingRepo.findAllByTenantId(tenantId);
    }

    @PostMapping
    public TelegramBotBinding create(@RequestBody CreateTelegramBindingDto dto) {
        UUID tenantId = requireBindingTenantId();
        if (dto.botToken() == null || dto.botToken().isBlank()) {
            throw new IllegalArgumentException("botToken is required");
        }

        ChatbotInstance bot = botRepo.findById(dto.chatbotId())
                .orElseThrow(() -> new IllegalArgumentException("Chatbot not found"));

        if (!bot.getTenantId().equals(tenantId)) {
            throw new IllegalArgumentException("Chatbot does not belong to this tenant");
        }

        String botToken = dto.botToken().trim();
        String publicBaseUrl = dto.publicBaseUrl() == null ? "" : dto.publicBaseUrl().trim();

        bindingRepo.findByBotTokenAndStatus(botToken, "ACTIVE").ifPresent(existing -> {
            if (existing.getTenantId().equals(tenantId) && existing.getChatbotId().equals(dto.chatbotId())) {
                return;
            }
            log.warn("botToken {} already bound to chatbot {}, unbinding old one", maskToken(botToken), existing.getChatbotId());
            existing.setStatus("INACTIVE");
            bindingRepo.save(existing);
        });

        TelegramBotBinding binding = bindingRepo.findByTenantIdAndChatbotId(tenantId, dto.chatbotId())
                .orElseGet(() -> {
                    TelegramBotBinding created = new TelegramBotBinding();
                    created.setId(UUID.randomUUID());
                    created.setTenantId(tenantId);
                    created.setChatbotId(dto.chatbotId());
                    created.setSecretPath(randomSecretPath());
                    return created;
                });

        binding.setBotToken(botToken);
        binding.setStatus("ACTIVE");
        bindingRepo.save(binding);

        String webhookUrl = sendService.buildWebhookUrl(publicBaseUrl, binding.getSecretPath());
        boolean webhookOk = sendService.setWebhook(botToken, publicBaseUrl, binding.getSecretPath());
        binding.setWebhookOk(webhookOk);
        binding.setWebhookUrl(webhookUrl);

        if (webhookOk) {
            log.info("Telegram webhook set successfully for botToken={} url={}", maskToken(botToken), webhookUrl);
        } else {
            log.warn("Telegram webhook set FAILED for botToken={} url={}. Bot will not receive messages until webhook is set manually.",
                    maskToken(botToken), webhookUrl);
        }

        return binding;
    }

    private String randomSecretPath() {
        byte[] buf = new byte[32];
        new SecureRandom().nextBytes(buf);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(buf);
    }

    private String maskToken(String botToken) {
        if (botToken == null || botToken.length() < 12) {
            return "[redacted]";
        }
        return botToken.substring(0, 8) + "...";
    }

    private UUID requireBindingTenantId() {
        AppPrincipal principal = principalAccessor.requireAnyRole(AppRole.PLATFORM_ADMIN, AppRole.TENANT_ADMIN);

        String tenantId = principal.role() == AppRole.PLATFORM_ADMIN
                ? TenantContext.get()
                : principal.tenantId();
        if (tenantId == null || tenantId.isBlank()) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "Tenant context required. Select a tenant or send X-Tenant-Id/X-API-Key."
            );
        }
        return UUID.fromString(tenantId);
    }
}
