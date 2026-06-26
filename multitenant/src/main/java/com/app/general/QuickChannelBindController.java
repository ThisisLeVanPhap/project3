package com.app.general;

import com.app.auth.SessionPrincipalAccessor;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/admin/quick-bind-channel")
public class QuickChannelBindController {

    private final QuickChannelBindService service;
    private final SessionPrincipalAccessor principalAccessor;

    public QuickChannelBindController(QuickChannelBindService service,
                                       SessionPrincipalAccessor principalAccessor) {
        this.service = service;
        this.principalAccessor = principalAccessor;
    }

    @PostMapping
    public QuickChannelBindResponse bind(@RequestBody QuickChannelBindRequest request) {
        principalAccessor.requirePlatformAdmin();
        return service.bind(request);
    }
}
