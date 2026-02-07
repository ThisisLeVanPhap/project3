package com.app.modelserver.dto;

public record FeedbackRequest(
        String conversation_id,
        String tenant_id,
        String channel,
        String question,
        String answer,
        boolean is_correct,
        String note
) {}
