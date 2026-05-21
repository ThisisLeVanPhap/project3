package com.app.onboarding;

import com.app.auth.SessionPrincipalAccessor;
import com.app.onboarding.TenantOnboardingService.ProvisionTenantFromOnboardingRequest;
import com.app.onboarding.TenantOnboardingService.TenantOnboardingResponse;
import com.app.onboarding.TenantOnboardingService.UpdateOnboardingStatusRequest;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/admin/onboarding-requests")
public class TenantOnboardingAdminController {

    private final TenantOnboardingService service;
    private final SessionPrincipalAccessor principalAccessor;

    public TenantOnboardingAdminController(
            TenantOnboardingService service,
            SessionPrincipalAccessor principalAccessor
    ) {
        this.service = service;
        this.principalAccessor = principalAccessor;
    }

    @GetMapping
    public List<TenantOnboardingResponse> list(@RequestParam(required = false) String status) {
        principalAccessor.requirePlatformAdmin();
        return service.list(status);
    }

    @PatchMapping("/{requestId}/status")
    public TenantOnboardingResponse updateStatus(
            @PathVariable UUID requestId,
            @RequestBody UpdateOnboardingStatusRequest request
    ) {
        principalAccessor.requirePlatformAdmin();
        return service.updateStatus(requestId, request);
    }

    @PostMapping("/{requestId}/provision")
    public TenantOnboardingResponse provision(
            @PathVariable UUID requestId,
            @RequestBody ProvisionTenantFromOnboardingRequest request
    ) {
        principalAccessor.requirePlatformAdmin();
        return service.provision(requestId, request);
    }
}
