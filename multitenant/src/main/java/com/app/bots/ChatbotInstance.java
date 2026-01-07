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

    @Id
    private UUID id;

    private String name;
    private String channel;                 // web/facebook/zalo...

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "persona", columnDefinition = "jsonb")
    private JsonNode persona;;                 // JSON: tone, flow, rules...

    private String status;

    @Column(name = "base_model")
    private String baseModel;              // vd: "TinyLlama/TinyLlama-1.1B-Chat-v1.0"

    @Column(name = "adapter_path")
    private String adapterPath;            // vd: "out/lora_tenant1_styleA"

    @Column(name = "tokenizer_path")
    private String tokenizerPath;          // vd: "out/tokenizer"

    @Column(name = "system_prompt", columnDefinition = "text")
    private String systemPrompt;           // prompt riêng của bot này

    @Column(name = "max_new_tokens")
    private Integer maxNewTokens;
    private Double temperature;

    @Column(name = "top_p")
    private Double topP;

    @Column(name = "top_k")
    private Integer topK;
}
