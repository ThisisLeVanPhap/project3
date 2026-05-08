package com.app.leads;

import com.app.chat.Message;
import com.app.chat.MessageRepository;
import com.app.modelserver.PythonChatClient;
import com.app.modelserver.dto.StateResponse;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.UUID;

@Service
public class LeadService {

    private final LeadRepository leadRepo;
    private final MessageRepository msgRepo;
    private final PythonChatClient python;
    private final ObjectMapper om = new ObjectMapper();

    public LeadService(LeadRepository leadRepo, MessageRepository msgRepo, PythonChatClient python) {
        this.leadRepo = leadRepo;
        this.msgRepo = msgRepo;
        this.python = python;
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
}
