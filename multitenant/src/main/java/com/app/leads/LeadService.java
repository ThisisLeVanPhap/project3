package com.app.leads;

import com.app.modelserver.PythonChatClient;
import com.app.modelserver.dto.StateResponse;
import com.app.chat.Message; // adjust to your actual Message entity import
import com.app.chat.MessageRepository; // adjust to your repo
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
        StateResponse st = python.getState(baseUrl, conversationId);

        String slotsJson;
        try { slotsJson = om.writeValueAsString(st.slots()); }
        catch (Exception e) { slotsJson = "{}"; }

        // last ~20 messages transcript
        List<Message> history = msgRepo.findTop20ByConversationIdOrderByCreatedAtAsc(UUID.fromString(conversationId));
        StringBuilder sb = new StringBuilder();
        for (Message m : history) {
            sb.append(m.getRole()).append(": ").append(m.getContent()).append("\n");
        }
        String transcript = sb.toString().trim();

        Lead lead = Lead.createNew(tenantId, channel, conversationId, customerHandle, slotsJson, transcript);
        return leadRepo.save(lead);
    }
}
