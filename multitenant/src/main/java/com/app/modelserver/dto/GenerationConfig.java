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
        List<String> stop,          // NEW: stop sequences
        Boolean return_full_text    // NEW (optional): yêu cầu python chỉ trả phần completion
) {}
