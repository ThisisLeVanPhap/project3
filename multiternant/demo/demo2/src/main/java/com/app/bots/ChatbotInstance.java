package com.app.bots;

import com.app.common.TenantEntityListener;
import com.app.common.TenantScoped;
import com.fasterxml.jackson.databind.JsonNode;
import jakarta.persistence.*;
import lombok.Getter; import lombok.Setter;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.util.UUID;

@Entity
@Table(name="chatbot_instances")
@EntityListeners(TenantEntityListener.class)
@Getter @Setter
public class ChatbotInstance extends TenantScoped {
    @Id private UUID id;

    private String name;
    private String channel;        // web/facebook/zalo

    @JdbcTypeCode(SqlTypes.JSON)                 // <= QUAN TRỌNG
    @Column(columnDefinition="jsonb", nullable=false)
    private JsonNode persona;                    // thay String -> JsonNode

    private String status;
}
