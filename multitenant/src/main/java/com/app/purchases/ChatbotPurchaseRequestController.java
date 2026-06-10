package com.app.purchases;

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
    private final String serviceToken;

    public ChatbotPurchaseRequestController(
            PurchaseRequestService purchaseRequestService,
            @Value("${app.chatbot.service-token:${CHATBOT_SERVICE_TOKEN:}}") String serviceToken
    ) {
        this.purchaseRequestService = purchaseRequestService;
        this.serviceToken = serviceToken;
    }

    @PostMapping
    public ResponseEntity<ChatbotPurchaseRequestCreateResponse> create(
            @RequestHeader(value = "Authorization", required = false) String authorization,
            @RequestHeader(value = "X-Service-Token", required = false) String serviceTokenHeader,
            @RequestBody ChatbotPurchaseRequestCreateRequest request
    ) {
        requireValidServiceToken(authorization, serviceTokenHeader);
        PurchaseRequestService.ChatbotCreateResult result =
                purchaseRequestService.createFromChatbotHandoff(request);
        HttpStatus status = result.created() ? HttpStatus.CREATED : HttpStatus.OK;
        return ResponseEntity.status(status).body(ChatbotPurchaseRequestCreateResponse.from(result));
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
