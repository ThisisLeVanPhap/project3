package com.app.messenger;

import com.app.auth.AppPrincipal;
import com.app.auth.AppRole;
import com.app.auth.SessionPrincipalAccessor;
import com.app.bots.ChatbotInstance;
import com.app.bots.ChatbotInstanceRepository;
import com.app.kb.ResolvedTenantKbDirectory;
import com.app.kb.TenantKbDirectoryResolver;
import com.app.messenger.dto.CreateMessengerBindingDto;
import com.app.messenger.dto.MessengerBindingStatusResponse;
import com.app.messenger.dto.MessengerPageBindingResponse;
import com.app.modelserver.LlmInstanceManager;
import com.app.tenant.TenantContext;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/messenger/bindings")
@RequiredArgsConstructor
public class MessengerBindingController {

    private final MessengerPageBindingRepository bindingRepo;
    private final ChatbotInstanceRepository botRepo;
    private final SessionPrincipalAccessor principalAccessor;
    private final TenantKbDirectoryResolver tenantKbDirectoryResolver;
    private final LlmInstanceManager llmInstanceManager;

    @GetMapping
    public List<MessengerPageBindingResponse> listMine() {
        UUID tenantId = requireBindingTenantId();
        return bindingRepo.findAllByTenantId(tenantId).stream()
                .map(MessengerPageBindingResponse::from)
                .toList();
    }

    @PostMapping
    public MessengerPageBindingResponse create(@RequestBody CreateMessengerBindingDto dto) {
        UUID tenantId = requireBindingTenantId();

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

        return MessengerPageBindingResponse.from(bindingRepo.save(b));
    }

    @DeleteMapping("/{id}")
    public void deactivate(@PathVariable UUID id) {
        UUID tenantId = requireBindingTenantId();

        MessengerPageBinding b = bindingRepo.findById(id)
                .orElseThrow(() -> new IllegalArgumentException("Binding not found"));

        if (!b.getTenantId().equals(tenantId)) {
            throw new IllegalArgumentException("Binding does not belong to this tenant");
        }

        b.setStatus("INACTIVE");
        bindingRepo.save(b);
    }

    @GetMapping("/{pageId}/status")
    public MessengerBindingStatusResponse status(@PathVariable String pageId) {
        AppPrincipal principal = principalAccessor.requireAnyRole(AppRole.PLATFORM_ADMIN, AppRole.TENANT_ADMIN);
        return bindingRepo.findByPageIdAndStatus(pageId, "ACTIVE")
                .map(binding -> {
                    enforceReadableBindingScope(principal, binding);
                    ResolvedTenantKbDirectory desiredKb = tenantKbDirectoryResolver.resolve(binding.getTenantId());
                    LlmInstanceManager.RuntimeKbStatusSnapshot runtimeStatus =
                            llmInstanceManager.getRuntimeKbStatus(binding.getTenantId());
                    return MessengerBindingStatusResponse.active(binding, desiredKb, runtimeStatus);
                })
                .orElseGet(() -> MessengerBindingStatusResponse.inactive(pageId, "NO_ACTIVE_BINDING"));
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

    private void enforceReadableBindingScope(AppPrincipal principal, MessengerPageBinding binding) {
        if (principal.role() == AppRole.PLATFORM_ADMIN) {
            return;
        }
        if (principal.tenantId() == null || principal.tenantId().isBlank()) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Tenant-bound principal required");
        }
        if (!binding.getTenantId().toString().equals(principal.tenantId())) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Binding does not belong to this tenant");
        }
    }
}
