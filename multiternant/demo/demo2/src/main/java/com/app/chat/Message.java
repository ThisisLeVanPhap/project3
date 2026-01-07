package com.app.chat;

import com.app.common.TenantEntityListener;
import com.app.common.TenantScoped;
import jakarta.persistence.*;
import lombok.*;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name="messages")
@EntityListeners(TenantEntityListener.class)
@Getter
@Setter
@NoArgsConstructor
public class Message extends TenantScoped {

    @Id
    private UUID id;

    @Column(name = "conversation_id", nullable = false)
    private UUID conversationId;

    // user / assistant / system
    @Column(nullable = false, length = 16)
    private String role;

    @Column(columnDefinition = "text", nullable = false)
    private String content;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @PrePersist
    void prePersist() {
        if (this.createdAt == null) {
            this.createdAt = Instant.now();
        }
        if (this.id == null) {
            this.id = UUID.randomUUID();
        }
    }

    // 👇 Constructor custom đúng với chỗ ChatController đang dùng
    public Message(UUID id, UUID conversationId, String role, String content) {
        this.id = id;
        this.conversationId = conversationId;
        this.role = role;
        this.content = content;
        this.createdAt = Instant.now();   // khớp với NOT NULL
    }
}
