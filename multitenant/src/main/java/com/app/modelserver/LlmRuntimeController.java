package com.app.modelserver;

import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/runtime/llm")
@RequiredArgsConstructor
public class LlmRuntimeController {

    private final LlmInstanceManager llm;

    @GetMapping
    public Map<UUID, LlmInstanceManager.Running> listRunning() {
        return llm.dumpRunning();
    }
}
