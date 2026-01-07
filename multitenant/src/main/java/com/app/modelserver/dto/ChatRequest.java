package com.app.modelserver.dto;

import java.util.List;

public record ChatRequest(
        String message,
        List<String> history,
        GenerationConfig gen
) {}
