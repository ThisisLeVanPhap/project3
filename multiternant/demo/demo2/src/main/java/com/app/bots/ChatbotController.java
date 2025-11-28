package com.app.bots;

import com.app.bots.dto.CreateChatbotDto;
import com.app.tenant.TenantContext;
import com.app.tenant.TenantGuards;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.*;

@RestController
@RequestMapping("/api/chatbots")
@RequiredArgsConstructor
public class ChatbotController {
    private final ChatbotInstanceRepository repo;
    private final ObjectMapper mapper;

    private UUID requireTenant() {
        return TenantGuards.requireTenant();
    }

    @PostMapping
    public ChatbotInstance create(@RequestBody CreateBotDto dto) throws Exception {
        var c = new ChatbotInstance();
        c.setId(UUID.randomUUID());
        c.setName(dto.name());
        c.setChannel(dto.channel());
        c.setStatus("ACTIVE");

        // personaJson -> JsonNode (nếu null thì {})
        JsonNode persona = (dto.personaJson() != null && !dto.personaJson().isBlank())
                ? mapper.readTree(dto.personaJson())
                : mapper.createObjectNode();
        c.setPersona(persona);

        // tenantId auto by listener
        return repo.save(c);
    }

    @GetMapping
    public List<ChatbotInstance> list() {
        return repo.findAllByTenant(UUID.fromString(TenantContext.get()));
    }

    public record CreateBotDto(String name, String channel, String personaJson) {}
}
