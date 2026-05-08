package com.app.bots;

import com.app.auth.SessionPrincipalAccessor;
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
        principalAccessor.requireTenantAdmin();

        var c = new ChatbotInstance();
        c.setId(UUID.randomUUID());
        c.setStatus("ACTIVE");
        applyDto(c, dto);
        return repo.save(c);
    }

    @PutMapping("/{id}")
    public ChatbotInstance update(@PathVariable UUID id, @RequestBody SaveBotDto dto) throws Exception {
        principalAccessor.requireTenantAdmin();

        UUID tenantId = UUID.fromString(TenantContext.get());
        ChatbotInstance chatbot = repo.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Chatbot not found"));
        if (!tenantId.equals(chatbot.getTenantId())) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Chatbot not found");
        }
        applyDto(chatbot, dto);
        return repo.save(chatbot);
    }

    @GetMapping
    public List<ChatbotInstance> list() {
        principalAccessor.requireTenantAdmin();
        return repo.findAllByTenant(UUID.fromString(TenantContext.get()));
    }

    private void applyDto(ChatbotInstance chatbot, SaveBotDto dto) throws Exception {
        chatbot.setName(dto.name());
        chatbot.setChannel(dto.channel());
        chatbot.setPersona(parsePersona(dto.personaJson()));
        chatbot.setResponseStyle(normalizeResponseStyle(dto.responseStyle()));

        // Mode
        if (dto.mode() != null && !dto.mode().isBlank()) {
            chatbot.setMode(dto.mode());
        } else {
            chatbot.setMode("tenant_sales");
        }

        // Provider and API config
        if (dto.provider() != null && !dto.provider().isBlank()) {
            chatbot.setProvider(dto.provider());
        } else {
            chatbot.setProvider("local");
        }
        chatbot.setApiModel(blankToNull(dto.apiModel()));
        // Only update apiKey if a non-empty value is provided; preserve existing if blank
        if (dto.apiKey() != null && !dto.apiKey().isBlank()) {
            chatbot.setApiKey(dto.apiKey());
        }
        chatbot.setApiBaseUrl(blankToNull(dto.apiBaseUrl()));
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
