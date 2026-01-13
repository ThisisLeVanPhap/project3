package com.app.telegram;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface TelegramBotBindingRepository extends JpaRepository<TelegramBotBinding, UUID> {

    Optional<TelegramBotBinding> findBySecretPathAndStatus(String secretPath, String status);

    List<TelegramBotBinding> findAllByTenantId(UUID tenantId);

    Optional<TelegramBotBinding> findByTenantIdAndChatbotId(UUID tenantId, UUID chatbotId);
}
