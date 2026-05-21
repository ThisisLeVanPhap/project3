package com.app.onboarding;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface TenantOnboardingRequestRepository extends JpaRepository<TenantOnboardingRequest, UUID> {
    List<TenantOnboardingRequest> findAllByOrderByCreatedAtDesc();

    List<TenantOnboardingRequest> findAllByStatusOrderByCreatedAtDesc(String status);
}
