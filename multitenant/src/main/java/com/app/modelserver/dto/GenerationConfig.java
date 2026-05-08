package com.app.modelserver.dto;

import java.util.List;

public record GenerationConfig(
        String base_model,
        String adapter,
        String tokenizer_path,
        String system_prompt,
        Integer max_new_tokens,
        Double temperature,
        Double top_p,
        Integer top_k,
        String response_style,
        List<String> stop,
        String provider,
        String api_model,
        String api_key,
        String api_base_url,
        String mode
) {}
