package com.app.chat;

import com.app.chat.dto.SendMessageDto;
import com.app.chat.dto.StartConversationDto;
import com.app.tenant.TenantContext;
import com.app.tenant.TenantGuards;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/chat")
@RequiredArgsConstructor
public class ChatController {
    private final ConversationRepository convRepo;
    private final MessageRepository msgRepo;

    @PostMapping("/start")
    public Map<String,Object> start(@Valid @RequestBody StartConversationDto req) {
        TenantGuards.requireTenant();

        Conversation c = new Conversation();
        c.setId(UUID.randomUUID());
        c.setChatbotId(UUID.fromString(req.chatbotId()));
        c.setTenantId(UUID.fromString(TenantContext.get()));
        c.setUserExternalId(req.userExternalId());
        convRepo.save(c);

        return Map.of("conversationId", c.getId());
    }

    @PostMapping("/send")
    public Map<String,Object> send(@Valid @RequestBody SendMessageDto req) {
        TenantGuards.requireTenant();

        UUID convId = UUID.fromString(req.conversationId());

        // user message
        Message m1 = new Message(UUID.randomUUID(), convId, "user", req.message());
        m1.setTenantId(UUID.fromString(TenantContext.get()));
        msgRepo.save(m1);

        // TODO: thay bằng ReplyGenerator (LLM/vLLM) sau
        String reply = "Cảm ơn bạn! (stub) Cho mình biết ngân sách dự kiến?";

        // assistant reply
        Message m2 = new Message(UUID.randomUUID(), convId, "assistant", reply);
        m2.setTenantId(UUID.fromString(TenantContext.get()));
        msgRepo.save(m2);

        return Map.of("reply", reply);
    }
}
