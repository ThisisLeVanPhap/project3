package com.app.messenger.dto;

import com.app.kb.ResolvedTenantKbDirectory;
import com.app.modelserver.LlmInstanceManager;
import com.app.messenger.MessengerPageBinding;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.UUID;

public record MessengerBindingStatusResponse(
        @JsonProperty("page_id")
        String pageId,
        @JsonProperty("binding_active")
        boolean bindingActive,
        String reason,
        @JsonProperty("tenant_id")
        UUID tenantId,
        @JsonProperty("chatbot_id")
        UUID chatbotId,
        @JsonProperty("binding_status")
        String bindingStatus,
        @JsonProperty("token_configured")
        Boolean tokenConfigured,
        @JsonProperty("token_preview")
        String tokenPreview,
        @JsonProperty("desired_kb")
        ResolvedTenantKbDirectory desiredKb,
        LlmInstanceManager.RuntimeKbRunningSnapshot runtime,
        @JsonProperty("runtime_in_sync")
        Boolean runtimeInSync
) {
    public static MessengerBindingStatusResponse inactive(String pageId, String reason) {
        return new MessengerBindingStatusResponse(
                pageId,
                false,
                reason,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null
        );
    }

    public static MessengerBindingStatusResponse active(
            MessengerPageBinding binding,
            ResolvedTenantKbDirectory desiredKb,
            LlmInstanceManager.RuntimeKbStatusSnapshot runtimeStatus
    ) {
        String token = binding.getPageAccessToken();
        return new MessengerBindingStatusResponse(
                binding.getPageId(),
                true,
                null,
                binding.getTenantId(),
                binding.getChatbotId(),
                binding.getStatus(),
                token != null && !token.isBlank(),
                MessengerPageBindingResponse.maskToken(token),
                desiredKb,
                runtimeStatus.running(),
                runtimeStatus.inSync()
        );
    }
}
