package com.app.chat;

public record ConversationResetResponse(
        boolean success,
        String tenantId,
        String conversationId,
        long messagesDeleted,
        boolean runtimeCacheCleared,
        long leadsDeleted,
        long purchaseRequestsDeleted,
        String message
) {
    public static ConversationResetResponse success(String tenantId, String conversationId, long messagesDeleted) {
        return success(tenantId, conversationId, messagesDeleted, false);
    }

    public static ConversationResetResponse success(
            String tenantId,
            String conversationId,
            long messagesDeleted,
            boolean runtimeCacheCleared
    ) {
        return new ConversationResetResponse(
                true,
                tenantId,
                conversationId,
                messagesDeleted,
                runtimeCacheCleared,
                0,
                0,
                "Conversation reset for testing"
        );
    }
}
