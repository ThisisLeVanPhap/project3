package com.app.messenger;

import com.app.auth.SessionPrincipalAccessor;
import com.app.bots.ChatbotInstance;
import com.app.bots.ChatbotInstanceRepository;
import com.app.messenger.dto.CreateMessengerBindingDto;
import com.app.tenant.TenantContext;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/messenger/bindings")
@RequiredArgsConstructor
public class MessengerBindingController {

    private final MessengerPageBindingRepository bindingRepo;
    private final ChatbotInstanceRepository botRepo;
    private final SessionPrincipalAccessor principalAccessor;

    @GetMapping
    public List<MessengerPageBinding> listMine() {
        principalAccessor.requireTenantAdmin();
        UUID tenantId = UUID.fromString(TenantContext.get());
        return bindingRepo.findAllByTenantId(tenantId);
    }

    @PostMapping
    public MessengerPageBinding create(@RequestBody CreateMessengerBindingDto dto) {
        principalAccessor.requireTenantAdmin();
        UUID tenantId = UUID.fromString(TenantContext.get());

        ChatbotInstance bot = botRepo.findById(dto.chatbotId())
                .orElseThrow(() -> new IllegalArgumentException("Chatbot not found"));
        if (!bot.getTenantId().equals(tenantId)) {
            throw new IllegalArgumentException("Chatbot does not belong to this tenant");
        }

        bindingRepo.findByPageIdAndStatus(dto.pageId(), "ACTIVE")
                .ifPresent(x -> { throw new IllegalArgumentException("This pageId is already bound"); });

        MessengerPageBinding b = new MessengerPageBinding();
        b.setId(UUID.randomUUID());
        b.setTenantId(tenantId);
        b.setPageId(dto.pageId());
        b.setChatbotId(dto.chatbotId());
        b.setPageAccessToken(dto.pageAccessToken());
        b.setStatus("ACTIVE");

        return bindingRepo.save(b);
    }

    @DeleteMapping("/{id}")
    public void deactivate(@PathVariable UUID id) {
        principalAccessor.requireTenantAdmin();
        UUID tenantId = UUID.fromString(TenantContext.get());

        MessengerPageBinding b = bindingRepo.findById(id)
                .orElseThrow(() -> new IllegalArgumentException("Binding not found"));

        if (!b.getTenantId().equals(tenantId)) {
            throw new IllegalArgumentException("Binding does not belong to this tenant");
        }

        b.setStatus("INACTIVE");
        bindingRepo.save(b);
    }
}
