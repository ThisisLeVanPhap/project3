package com.app.bots;

import com.app.auth.AppRole;
import com.app.auth.SessionPrincipalAccessor;
import com.app.modelserver.ChatbotMode;
import com.app.tenant.TenantContext;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.util.*;

@RestController
@RequestMapping("/api/chatbots")
@RequiredArgsConstructor
public class ChatbotController {
    private final ChatbotInstanceRepository repo;
    private final ObjectMapper mapper;
    private final SessionPrincipalAccessor principalAccessor;

    public record SaveBotDto(
            String name,
            String channel,
            String personaJson,
            String responseStyle,
            String mode,
            String provider,
            String apiModel,
            String apiKey,
            String apiBaseUrl
    ) {}

    @PostMapping
    public ChatbotInstance create(@RequestBody SaveBotDto dto) throws Exception {
        UUID tenantId = requireChatbotManagerTenantId();

        var c = new ChatbotInstance();
        c.setId(UUID.randomUUID());
        c.setTenantId(tenantId);
        c.setStatus("ACTIVE");
        applyDto(c, dto);
        return repo.save(c);
    }

    @PutMapping("/{id}")
    public ChatbotInstance update(@PathVariable UUID id, @RequestBody SaveBotDto dto) throws Exception {
        UUID tenantId = requireChatbotManagerTenantId();

        ChatbotInstance chatbot = repo.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Chatbot not found"));
        if (!tenantId.equals(chatbot.getTenantId())) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Chatbot not found");
        }
        applyDto(chatbot, dto);
        return repo.save(chatbot);
    }

    @DeleteMapping("/{id}")
    public Map<String, Object> delete(@PathVariable UUID id) {
        UUID tenantId = requireChatbotManagerTenantId();

        ChatbotInstance chatbot = repo.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Chatbot not found"));
        if (!tenantId.equals(chatbot.getTenantId())) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Chatbot not found");
        }

        repo.delete(chatbot);
        return Map.of("deleted", true, "id", id);
    }

    @GetMapping
    public List<ChatbotInstance> list() {
        UUID tenantId = requireChatbotManagerTenantId();
        return repo.findAllByTenant(tenantId);
    }

    private UUID requireChatbotManagerTenantId() {
        principalAccessor.requireAnyRole(AppRole.PLATFORM_ADMIN, AppRole.TENANT_ADMIN);
        String tenantId = TenantContext.get();
        if (tenantId == null || tenantId.isBlank()) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "Tenant context required. Select a tenant first."
            );
        }
        return UUID.fromString(tenantId);
    }

    private void applyDto(ChatbotInstance chatbot, SaveBotDto dto) throws Exception {
        chatbot.setName(dto.name());
        chatbot.setChannel(dto.channel());
        chatbot.setPersona(parsePersona(dto.personaJson()));
        chatbot.setResponseStyle(normalizeResponseStyle(dto.responseStyle()));

        // Mode
        if (dto.mode() != null && !dto.mode().isBlank()) {
            chatbot.setMode(ChatbotMode.normalize(dto.mode()));
        } else {
            chatbot.setMode(ChatbotMode.TENANT_SALES);
        }

        // Provider
        if (dto.provider() != null && !dto.provider().isBlank()) {
            chatbot.setProvider(dto.provider());
        } else {
            chatbot.setProvider("claude");
        }
        // Claude config is system-level only (env-based). Do not persist per-chatbot API fields.
        if ("claude".equalsIgnoreCase(chatbot.getProvider())) {
            chatbot.setApiModel(null);
            chatbot.setApiKey(null);
            chatbot.setApiBaseUrl(null);
        }
    }

    private String blankToNull(String s) {
        return (s == null || s.isBlank()) ? null : s;
    }

    private JsonNode parsePersona(String personaJson) throws Exception {
        return (personaJson != null && !personaJson.isBlank())
                ? mapper.readTree(personaJson)
                : mapper.createObjectNode();
    }

    private String normalizeResponseStyle(String responseStyle) {
        if (responseStyle == null || responseStyle.isBlank()) {
            return "natural";
        }
        String normalized = responseStyle.trim().toLowerCase(Locale.ROOT);
        if (!Set.of("natural", "balanced", "fast").contains(normalized)) {
            throw new IllegalArgumentException("Unsupported responseStyle: " + responseStyle);
        }
        return normalized;
    }
}
