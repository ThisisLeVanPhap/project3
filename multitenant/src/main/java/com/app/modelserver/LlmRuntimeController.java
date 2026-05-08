package com.app.modelserver;

import com.app.auth.SessionPrincipalAccessor;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/runtime/llm")
@RequiredArgsConstructor
public class LlmRuntimeController {

    private final LlmInstanceManager llm;
    private final SessionPrincipalAccessor principalAccessor;

    @GetMapping
    public Map<UUID, LlmInstanceManager.Running> listRunning() {
        principalAccessor.requirePlatformAdmin();
        return llm.dumpRunning();
    }
}
