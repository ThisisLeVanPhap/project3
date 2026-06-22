package com.app.chat;

public record ConversationResetRequest(
        String conversationId,
        String channel,
        String externalUserId,
        String chatbotId,
        Boolean deleteMessages,
        Boolean resetBusinessFlags
) {
    public boolean shouldDeleteMessages() {
        return deleteMessages == null || deleteMessages;
    }

    public boolean shouldResetBusinessFlags() {
        return Boolean.TRUE.equals(resetBusinessFlags);
    }
}
