package com.app.chat;

import com.app.common.TenantEntityListener;
import com.app.common.TenantScoped;
import jakarta.persistence.*;
import lombok.Getter; import lombok.Setter;

import java.util.UUID;

@Entity
@Table(name="conversations")
@EntityListeners(TenantEntityListener.class)
@Getter @Setter
public class Conversation extends TenantScoped {
    @Id private UUID id;
    @Column(name="chatbot_id", nullable=false)
    private UUID chatbotId;
    private String userExternalId;
}
