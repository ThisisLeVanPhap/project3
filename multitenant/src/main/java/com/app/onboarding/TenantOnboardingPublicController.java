package com.app.onboarding;

import com.app.onboarding.TenantOnboardingService.CreateOnboardingRequest;
import com.app.onboarding.TenantOnboardingService.TenantOnboardingResponse;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/onboarding-requests")
public class TenantOnboardingPublicController {

    private final TenantOnboardingService service;

    public TenantOnboardingPublicController(TenantOnboardingService service) {
        this.service = service;
    }

    @PostMapping
    public TenantOnboardingResponse create(@RequestBody CreateOnboardingRequest request) {
        return service.create(request);
    }
}
