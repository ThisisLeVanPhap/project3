package com.app.messenger;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface MessengerPageBindingRepository extends JpaRepository<MessengerPageBinding, UUID> {

    Optional<MessengerPageBinding> findByPageIdAndStatus(String pageId, String status);

    Optional<MessengerPageBinding> findByTenantIdAndPageId(UUID tenantId, String pageId);

    List<MessengerPageBinding> findAllByTenantId(UUID tenantId);

    Optional<MessengerPageBinding> findByPageId(String pageId);

    long countByStatus(String status);

    @Query("select count(b) from MessengerPageBinding b where b.pageAccessToken is not null and trim(b.pageAccessToken) <> ''")
    long countWithConfiguredToken();
}
