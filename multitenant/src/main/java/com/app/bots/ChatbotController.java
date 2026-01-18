package com.app.bots;

import com.app.tenant.TenantContext;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.*;

@RestController
@RequestMapping("/api/chatbots")
@RequiredArgsConstructor
public class ChatbotController {
    private final ChatbotInstanceRepository repo;
    private final ObjectMapper mapper;

    public record CreateBotDto(String name, String channel, String personaJson) {}

    @PostMapping
    public ChatbotInstance create(@RequestBody CreateBotDto dto) throws Exception {
        var c = new ChatbotInstance();
        c.setId(UUID.randomUUID());
        c.setName(dto.name());
        c.setChannel(dto.channel());
        c.setStatus("ACTIVE");

        JsonNode persona = (dto.personaJson() != null && !dto.personaJson().isBlank())
                ? mapper.readTree(dto.personaJson())
                : mapper.createObjectNode();
        c.setPersona(persona);

        return repo.save(c);
    }

    @GetMapping
    public List<ChatbotInstance> list() {
        return repo.findAllByTenant(UUID.fromString(TenantContext.get()));
    }
}
