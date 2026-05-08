package com.app.modelserver;

public class ChatbotUpstreamException extends RuntimeException {

    private final UpstreamFailureCategory category;
    private final String tenantId;
    private final String baseUrl;
    private final Integer upstreamStatus;
    private final boolean coldStart;
    private final boolean warmupWaited;

    public ChatbotUpstreamException(
            UpstreamFailureCategory category,
            String tenantId,
            String baseUrl,
            Integer upstreamStatus,
            boolean coldStart,
            boolean warmupWaited,
            String message,
            Throwable cause
    ) {
        super(message, cause);
        this.category = category;
        this.tenantId = tenantId;
        this.baseUrl = baseUrl;
        this.upstreamStatus = upstreamStatus;
        this.coldStart = coldStart;
        this.warmupWaited = warmupWaited;
    }

    public UpstreamFailureCategory getCategory() {
        return category;
    }

    public String getTenantId() {
        return tenantId;
    }

    public String getBaseUrl() {
        return baseUrl;
    }

    public Integer getUpstreamStatus() {
        return upstreamStatus;
    }

    public boolean isColdStart() {
        return coldStart;
    }

    public boolean isWarmupWaited() {
        return warmupWaited;
    }
}
