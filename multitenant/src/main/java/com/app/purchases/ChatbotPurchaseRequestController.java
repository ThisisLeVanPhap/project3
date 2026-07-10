package com.app.purchases;

import com.app.leads.ChatbotLeadCreateResponse;
import com.app.leads.Lead;
import com.app.leads.LeadRepository;
import com.app.leads.LeadService;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/chatbot/purchase-requests")
public class ChatbotPurchaseRequestController {

    private final PurchaseRequestService purchaseRequestService;
    private final LeadService leadService;
    private final LeadRepository leadRepository;
    private final String serviceToken;

    public ChatbotPurchaseRequestController(
            PurchaseRequestService purchaseRequestService,
            LeadService leadService,
            LeadRepository leadRepository,
            @Value("${app.chatbot.service-token:${CHATBOT_SERVICE_TOKEN:}}") String serviceToken
    ) {
        this.purchaseRequestService = purchaseRequestService;
        this.leadService = leadService;
        this.leadRepository = leadRepository;
        this.serviceToken = serviceToken;
    }

    @PostMapping
    public ResponseEntity<ChatbotLeadCreateResponse> create(
            @RequestHeader(value = "Authorization", required = false) String authorization,
            @RequestHeader(value = "X-Service-Token", required = false) String serviceTokenHeader,
            @RequestBody ChatbotPurchaseRequestCreateRequest request
    ) {
        requireValidServiceToken(authorization, serviceTokenHeader);
        boolean existed = leadRepository
                .findTop1ByTenantIdAndConversationIdOrderByCreatedAtDesc(request.tenantId(), request.conversationId())
                .isPresent();
        Lead lead = leadService.createFromChatbotHandoff(new LeadService.ChatbotHandoffLeadData(
                request.tenantId(),
                request.conversationId(),
                request.channel(),
                "",
                "",
                request.customerName(),
                request.phone(),
                request.email(),
                request.requestedProductRef(),
                request.productSku(),
                request.productUrl(),
                request.price(),
                request.quantity(),
                request.notes(),
                request.handoffId(),
                request.idempotencyKey(),
                "",
                "HANDOFF",
                java.util.Map.of()
        ));
        HttpStatus status = existed ? HttpStatus.OK : HttpStatus.CREATED;
        return ResponseEntity.status(status).body(new ChatbotLeadCreateResponse(
                lead.getId(),
                request.handoffId(),
                request.idempotencyKey(),
                lead.getStatus(),
                lead.getStage(),
                !existed,
                lead
        ));
    }

    private void requireValidServiceToken(String authorization, String serviceTokenHeader) {
        if (!StringUtils.hasText(serviceToken)) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Chatbot service token is not configured");
        }

        String provided = extractBearerToken(authorization);
        if (!StringUtils.hasText(provided)) {
            provided = serviceTokenHeader;
        }
        if (!StringUtils.hasText(provided)) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Missing chatbot service token");
        }
        if (!constantTimeEquals(serviceToken.trim(), provided.trim())) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Invalid chatbot service token");
        }
    }

    private String extractBearerToken(String authorization) {
        if (!StringUtils.hasText(authorization)) {
            return "";
        }
        String trimmed = authorization.trim();
        if (trimmed.regionMatches(true, 0, "Bearer ", 0, "Bearer ".length())) {
            return trimmed.substring("Bearer ".length()).trim();
        }
        return "";
    }

    private boolean constantTimeEquals(String expected, String provided) {
        if (expected.length() != provided.length()) {
            return false;
        }
        int diff = 0;
        for (int i = 0; i < expected.length(); i++) {
            diff |= expected.charAt(i) ^ provided.charAt(i);
        }
        return diff == 0;
    }
}
