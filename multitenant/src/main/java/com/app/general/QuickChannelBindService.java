package com.app.general;

import com.app.bots.ChatbotInstance;
import com.app.bots.ChatbotInstanceRepository;
import com.app.messenger.MessengerPageBinding;
import com.app.messenger.MessengerPageBindingRepository;
import com.app.telegram.TelegramBotBinding;
import com.app.telegram.TelegramSendService;
import org.springframework.beans.factory.annotation.Value;
import com.app.telegram.TelegramBotBindingRepository;
import com.app.tenants.Tenant;
import com.app.tenants.TenantRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.util.UUID;

@Service
public class QuickChannelBindService {

    private static final Logger log = LoggerFactory.getLogger(QuickChannelBindService.class);

    private final TelegramBotBindingRepository telegramBindingRepo;
    private final MessengerPageBindingRepository messengerBindingRepo;
    private final ChatbotInstanceRepository botRepo;
    private final TenantRepository tenantRepo;
    private final TelegramSendService telegramSendService;
    private final String publicBaseUrl;

    public QuickChannelBindService(
            TelegramBotBindingRepository telegramBindingRepo,
            MessengerPageBindingRepository messengerBindingRepo,
            ChatbotInstanceRepository botRepo,
            TenantRepository tenantRepo,
            TelegramSendService telegramSendService,
            @Value("${app.public-base-url:http://localhost:8080}") String publicBaseUrl
    ) {
        this.telegramBindingRepo = telegramBindingRepo;
        this.messengerBindingRepo = messengerBindingRepo;
        this.botRepo = botRepo;
        this.tenantRepo = tenantRepo;
        this.telegramSendService = telegramSendService;
        this.publicBaseUrl = publicBaseUrl;
    }

    @Transactional
    public QuickChannelBindResponse bind(QuickChannelBindRequest req) {
        if (req.tenantId() == null || req.tenantId().isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "tenantId is required");
        }
        UUID tenantId = UUID.fromString(req.tenantId().trim());
        Tenant tenant = tenantRepo.findById(tenantId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Tenant not found"));

        if ("telegram".equalsIgnoreCase(req.channelType())) {
            return bindTelegram(tenant, req);
        } else if ("messenger".equalsIgnoreCase(req.channelType())) {
            return bindMessenger(tenant, req);
        } else {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Unsupported channel type: " + req.channelType());
        }
    }

    private QuickChannelBindResponse bindTelegram(Tenant tenant, QuickChannelBindRequest req) {
        String botToken = req.botToken() != null ? req.botToken().trim() : "";
        if (botToken.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "botToken is required for telegram");
        }
        String channelName = req.channelName() != null ? req.channelName().trim() : "Telegram Bot";

        // 1. Unbind existing binding for this botToken (by secret_path) — moves bot to new tenant
        telegramBindingRepo.findBySecretPath(botToken).ifPresent(existing -> {
            log.info("Rebinding telegram: removing existing binding for tenant {}", existing.getTenantId());
            UUID oldChatbotId = existing.getChatbotId();
            telegramBindingRepo.delete(existing);
            if (oldChatbotId != null) {
                botRepo.findById(oldChatbotId).ifPresent(botRepo::delete);
            }
        });

        // 2. Create new chatbot for this binding
        String tokenSuffix = botToken.length() > 8 ? botToken.substring(0, 8) : botToken;
        ChatbotInstance bot = createChatbot(tenant.getId(), channelName + " (" + tokenSuffix + ")", "telegram");

        // 3. Create binding
        TelegramBotBinding binding = new TelegramBotBinding();
        binding.setId(UUID.randomUUID());
        binding.setTenantId(tenant.getId());
        binding.setChatbotId(bot.getId());
        binding.setBotToken(botToken);
        binding.setSecretPath(botToken); // Use bot token as secret path
        binding.setStatus("ACTIVE");
        telegramBindingRepo.save(binding);

        // 4. Auto-set telegram webhook
        boolean webhookOk = telegramSendService.setWebhook(botToken);
        String webhookMsg = webhookOk
                ? "Webhook set automatically."
                : "Could not set Telegram webhook. Your bot may have no webhook configured.";

        // 5. Return webhook URL for reference
        String webhookUrl = publicBaseUrl + "/webhook/telegram/" + botToken;

        return new QuickChannelBindResponse(
                "telegram", tenant.getId(), bot.getId(), binding.getId(),
                webhookUrl,
                "Telegram bound to tenant " + tenant.getCode() + ". Chatbot '" + channelName + "' created. Set webhook: " + webhookUrl
        );
    }

    private QuickChannelBindResponse bindMessenger(Tenant tenant, QuickChannelBindRequest req) {
        String pageId = req.pageId() != null ? req.pageId().trim() : "";
        String pageAccessToken = req.pageAccessToken() != null ? req.pageAccessToken().trim() : "";
        if (pageId.isBlank() || pageAccessToken.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "pageId and pageAccessToken are required for messenger");
        }
        String channelName = req.channelName() != null ? req.channelName().trim() : "Messenger Page";

        // 1. Unbind existing binding for this pageId — moves page to new tenant
        messengerBindingRepo.findByPageIdAndStatus(pageId, "ACTIVE").ifPresent(existing -> {
            log.info("Rebinding messenger: removing existing binding for tenant {}", existing.getTenantId());
            UUID oldChatbotId = existing.getChatbotId();
            existing.setStatus("INACTIVE");
            messengerBindingRepo.save(existing);
            if (oldChatbotId != null) {
                botRepo.findById(oldChatbotId).ifPresent(botRepo::delete);
            }
        });

        // 2. Create new chatbot for this binding
        ChatbotInstance bot = createChatbot(tenant.getId(), channelName + " (" + pageId + ")", "messenger");

        // 3. Create binding
        MessengerPageBinding binding = new MessengerPageBinding();
        binding.setId(UUID.randomUUID());
        binding.setTenantId(tenant.getId());
        binding.setChatbotId(bot.getId());
        binding.setPageId(pageId);
        binding.setPageAccessToken(pageAccessToken);
        binding.setStatus("ACTIVE");
        messengerBindingRepo.save(binding);

        return new QuickChannelBindResponse(
                "messenger", tenant.getId(), bot.getId(), binding.getId(),
                null,
                "Messenger page " + pageId + " bound to tenant " + tenant.getCode() + ". Chatbot '" + channelName + "' created."
        );
    }

    private ChatbotInstance createChatbot(UUID tenantId, String name, String channel) {
        ChatbotInstance bot = new ChatbotInstance();
        bot.setId(UUID.randomUUID());
        bot.setTenantId(tenantId);
        bot.setName(name);
        bot.setChannel(channel);
        bot.setStatus("ACTIVE");
        bot.setMode("tenant_sales");
        bot.setProvider("claude");
        bot.setBaseModel("claude");
        return botRepo.save(bot);
    }
}
