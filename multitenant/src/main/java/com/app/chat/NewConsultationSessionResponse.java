package com.app.chat;

public record NewConsultationSessionResponse(
        String tenantId,
        String newConversationId,
        long closedConversationCount,
        long deletedMessageCount,
        long runtimeResetCount,
        long discardedLeadCount,
        long discardedPurchaseRequestCount
) {
}
