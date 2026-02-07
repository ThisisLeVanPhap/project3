package com.app.modelserver.dto;

import java.util.Map;

public record StateResponse(
        String stage,
        Map<String, Object> slots,
        Double updated_at,
        String last_question,
        String last_answer
) {}
