package com.app.admin;

import com.fasterxml.jackson.annotation.JsonProperty;

public record SystemStatusResponse(
        Tenants tenants,
        Chatbots chatbots,
        @JsonProperty("messenger_bindings")
        MessengerBindings messengerBindings,
        Kb kb,
        Runtime runtime,
        @JsonProperty("purchase_requests")
        PurchaseRequests purchaseRequests
) {
    public record Tenants(long total) {}

    public record Chatbots(long total) {}

    public record MessengerBindings(
            long total,
            long active,
            long inactive,
            @JsonProperty("token_configured")
            long tokenConfigured
    ) {}

    public record Kb(
            @JsonProperty("versions_total")
            long versionsTotal,
            long ready,
            long failed,
            long building,
            long archived
    ) {}

    public record Runtime(
            @JsonProperty("java_spawned_running")
            long javaSpawnedRunning,
            @JsonProperty("external_mode")
            boolean externalMode
    ) {}

    public record PurchaseRequests(
            long total,
            @JsonProperty("new")
            long newCount,
            long contacted,
            long completed
    ) {}
}
