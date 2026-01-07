package com.app.messenger;

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
        name = "messenger_page_bindings",
        uniqueConstraints = {
                @UniqueConstraint(name = "uq_binding_page_id", columnNames = {"page_id"}),
                @UniqueConstraint(name = "uq_binding_tenant_page", columnNames = {"tenant_id", "page_id"})
        }
)
@EntityListeners(TenantEntityListener.class) // tự set tenant_id theo TenantContext khi INSERT
public class MessengerPageBinding {

    @Id
    private UUID id;

    @Column(name = "tenant_id", nullable = false)
    private UUID tenantId;

    @Column(name = "page_id", nullable = false, length = 64)
    private String pageId;

    @Column(name = "chatbot_id", nullable = false)
    private UUID chatbotId;

    @Column(name = "page_access_token", nullable = false, columnDefinition = "text")
    private String pageAccessToken;

    @Column(name = "status", nullable = false, length = 32)
    private String status = "ACTIVE";

    @Column(name = "created_at", nullable = false)
    private Instant createdAt = Instant.now();
}
