package com.app.leads;

import com.app.chat.Message;
import com.app.chat.MessageRepository;
import com.app.chat.ConversationRepository;
import com.app.modelserver.PythonChatClient;
import com.app.modelserver.dto.StateResponse;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
public class LeadService {

    private final LeadRepository leadRepo;
    private final MessageRepository msgRepo;
    private final PythonChatClient python;
    private final ConversationRepository conversationRepo;
    private final ObjectMapper om = new ObjectMapper();

    public LeadService(
            LeadRepository leadRepo,
            MessageRepository msgRepo,
            PythonChatClient python,
            ConversationRepository conversationRepo
    ) {
        this.leadRepo = leadRepo;
        this.msgRepo = msgRepo;
        this.python = python;
        this.conversationRepo = conversationRepo;
    }

    public Lead createLeadFromConversation(String baseUrl,
                                           String tenantId,
                                           String channel,
                                           String conversationId,
                                           String customerHandle) {

        Lead lead = leadRepo.findTop1ByTenantIdAndConversationIdOrderByCreatedAtDesc(tenantId, conversationId)
                .orElseGet(() -> Lead.createNew(tenantId, channel, conversationId, customerHandle, "{}", ""));

        // Pull slots/state from python (optional but nice)
        StateResponse st = python.getState(baseUrl, conversationId);

        String slotsJson;
        try { slotsJson = om.writeValueAsString(st.slots()); }
        catch (Exception e) { slotsJson = "{}"; }

        UUID convId = UUID.fromString(conversationId);
        UUID tid = UUID.fromString(tenantId);

        List<Message> history =
                msgRepo.findTop200ByTenantIdAndConversationIdOrderByCreatedAtAsc(tid, convId);

        StringBuilder sb = new StringBuilder();
        for (Message m : history) {
            String role = m.getRole() == null ? "" : m.getRole().trim();
            String content = m.getContent() == null ? "" : m.getContent();

            // strip HTML tags
            content = content.replaceAll("<[^>]+>", "");
            content = content.replaceAll("\\s{2,}", " ").trim();
            if (content.isBlank()) continue;

            sb.append(role).append(": ").append(content).append("\n");
        }

        String transcript = sb.toString().trim();

        lead.setSlotsJson(slotsJson);
        lead.setTranscript(transcript);
        lead.setStage("HANDOFF");
        return leadRepo.save(lead);
    }

    public Lead createFromChatbotHandoff(ChatbotHandoffLeadData data) {
        String tenantId = firstNonBlank(data.tenantId(), com.app.tenant.TenantContext.get());
        String conversationId = safe(data.conversationId());
        if (tenantId.isBlank()) {
            throw new IllegalArgumentException("tenant_id is required");
        }
        if (conversationId.isBlank()) {
            throw new IllegalArgumentException("conversation_id is required");
        }

        Lead lead = leadRepo.findTop1ByTenantIdAndConversationIdOrderByCreatedAtDesc(tenantId, conversationId)
                .orElseGet(() -> Lead.createNew(
                        tenantId,
                        defaultIfBlank(data.channel(), "chatbot"),
                        conversationId,
                        safe(data.customerExternalId()),
                        "{}",
                        ""
                ));

        lead.setSlotsJson(toSlotsJson(data));
        lead.setTranscript(firstNonBlank(data.transcript(), buildTranscript(tenantId, conversationId)));
        lead.setStage(defaultIfBlank(data.stage(), "HANDOFF"));
        Lead saved = leadRepo.save(lead);
        markConversationLeadCreated(tenantId, conversationId);
        return saved;
    }

    private String toSlotsJson(ChatbotHandoffLeadData data) {
        Map<String, Object> slots = new LinkedHashMap<>();
        putIfPresent(slots, "source", "chatbot_handoff");
        putIfPresent(slots, "handoff_id", data.handoffId());
        putIfPresent(slots, "idempotency_key", data.idempotencyKey());
        putIfPresent(slots, "channel", data.channel());
        putIfPresent(slots, "customer_external_id", data.customerExternalId());
        putIfPresent(slots, "unified_customer_id", data.unifiedCustomerId());
        putIfPresent(slots, "customer_name", data.customerName());
        putIfPresent(slots, "phone", data.phone());
        putIfPresent(slots, "email", data.email());
        putIfPresent(slots, "requested_product_ref", data.requestedProductRef());
        putIfPresent(slots, "product_sku", data.productSku());
        putIfPresent(slots, "product_url", data.productUrl());
        putIfPresent(slots, "notes", data.notes());
        if (data.quantity() != null) {
            slots.put("quantity", data.quantity());
        }
        if (data.price() != null) {
            slots.put("price", data.price());
        }
        if (data.debug() != null && !data.debug().isEmpty()) {
            slots.put("debug", data.debug());
        }
        try {
            return om.writeValueAsString(slots);
        } catch (Exception e) {
            return "{}";
        }
    }

    private String buildTranscript(String tenantId, String conversationId) {
        try {
            UUID tid = UUID.fromString(tenantId);
            UUID convId = UUID.fromString(conversationId);
            List<Message> history =
                    msgRepo.findTop200ByTenantIdAndConversationIdOrderByCreatedAtAsc(tid, convId);
            StringBuilder sb = new StringBuilder();
            for (Message m : history) {
                String role = safe(m.getRole());
                String content = safe(m.getContent())
                        .replaceAll("<[^>]+>", "")
                        .replaceAll("\\s{2,}", " ")
                        .trim();
                if (!content.isBlank()) {
                    sb.append(role).append(": ").append(content).append("\n");
                }
            }
            return sb.toString().trim();
        } catch (RuntimeException ex) {
            return "";
        }
    }

    private void markConversationLeadCreated(String tenantId, String conversationId) {
        try {
            UUID tid = UUID.fromString(tenantId);
            UUID convId = UUID.fromString(conversationId);
            conversationRepo.findById(convId)
                    .filter(conversation -> tid.equals(conversation.getTenantId()))
                    .filter(conversation -> !conversation.isLeadCreated())
                    .ifPresent(conversation -> {
                        conversation.setLeadCreated(true);
                        conversationRepo.save(conversation);
                    });
        } catch (RuntimeException ignored) {
        }
    }

    private static void putIfPresent(Map<String, Object> target, String key, Object value) {
        if (value == null) {
            return;
        }
        String text = String.valueOf(value).trim();
        if (!text.isBlank()) {
            target.put(key, value);
        }
    }

    private static String defaultIfBlank(String value, String fallback) {
        String normalized = safe(value);
        return normalized.isBlank() ? fallback : normalized;
    }

    private static String firstNonBlank(String... values) {
        for (String value : values) {
            String normalized = safe(value);
            if (!normalized.isBlank()) {
                return normalized;
            }
        }
        return "";
    }

    private static String safe(String value) {
        return value == null ? "" : value.trim();
    }

    public record ChatbotHandoffLeadData(
            String tenantId,
            String conversationId,
            String channel,
            String customerExternalId,
            String unifiedCustomerId,
            String customerName,
            String phone,
            String email,
            String requestedProductRef,
            String productSku,
            String productUrl,
            java.math.BigDecimal price,
            Integer quantity,
            String notes,
            String handoffId,
            String idempotencyKey,
            String transcript,
            String stage,
            Map<String, Object> debug
    ) {
    }
}
