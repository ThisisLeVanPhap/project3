package com.app.chat;

import com.app.common.TenantEntityListener;
import com.app.common.TenantScoped;
import jakarta.persistence.*;
import lombok.*;

import java.util.UUID;

@Entity
@Table(name="messages")
@EntityListeners(TenantEntityListener.class)
@Getter @Setter
@NoArgsConstructor
@AllArgsConstructor
public class Message extends TenantScoped {
    @Id private UUID id;
    @Column(name="conversation_id", nullable=false)
    private UUID conversationId;
    private String role;     // user/assistant/system
    @Column(columnDefinition="text")
    private String content;
}
