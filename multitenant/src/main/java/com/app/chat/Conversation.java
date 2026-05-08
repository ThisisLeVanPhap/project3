package com.app.chat;

import com.app.common.TenantEntityListener;
import com.app.common.TenantScoped;
import jakarta.persistence.*;
import lombok.Getter;
import lombok.Setter;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "conversations")
@EntityListeners(TenantEntityListener.class)
@Getter
@Setter
public class Conversation extends TenantScoped {

    @Id
    private UUID id;

    @Column(name = "chatbot_id", nullable = false)
    private UUID chatbotId;

    private String userExternalId;

    // ✅ NEW: ACTIVE / CLOSED
    @Column(nullable = false)
    private String status = "ACTIVE";

    // ✅ NEW: track if lead/purchase request created for this conversation
    @Column(name = "lead_created", nullable = false)
    private boolean leadCreated = false;

    // ✅ NEW: conversation title (editable by user)
    @Column(name = "title", length = 200)
    private String title;

    // ✅ NEW: for ordering/debug
    @Column(name = "created_at", nullable = false)
    private Instant createdAt = Instant.now();
}
