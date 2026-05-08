package com.app.auth;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class MeController {

    private final SessionPrincipalAccessor principalAccessor;

    public MeController(SessionPrincipalAccessor principalAccessor) {
        this.principalAccessor = principalAccessor;
    }

    @GetMapping("/api/me")
    public AppPrincipal me() {
        return principalAccessor.requireCurrent();
    }
}
