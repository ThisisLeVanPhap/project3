package com.app.telegram;

import com.app.common.TenantEntityListener;
import jakarta.persistence.*;
import lombok.Getter;
import lombok.Setter;

import java.time.Instant;
import java.util.UUID;

@Getter
@Setter
@Entity
@Table(
        name = "telegram_bot_bindings",
        uniqueConstraints = {
                @UniqueConstraint(name = "uq_telegram_secret_path", columnNames = {"secret_path"}),
                @UniqueConstraint(name = "uq_telegram_tenant_chatbot", columnNames = {"tenant_id", "chatbot_id"})
        }
)
@EntityListeners(TenantEntityListener.class)
public class TelegramBotBinding {

    @Id
    private UUID id;

    @Column(name = "tenant_id", nullable = false)
    private UUID tenantId;

    @Column(name = "chatbot_id", nullable = false)
    private UUID chatbotId;

    @Column(name = "bot_username")
    private String botUsername;

    @Column(name = "bot_token", nullable = false, columnDefinition = "text")
    private String botToken;

    @Column(name = "secret_path", nullable = false, length = 128)
    private String secretPath;

    @Column(name = "status", nullable = false, length = 32)
    private String status = "ACTIVE";

    @Column(name = "created_at", nullable = false)
    private Instant createdAt = Instant.now();
}
