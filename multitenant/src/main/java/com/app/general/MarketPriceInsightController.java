package com.app.general;

import jakarta.servlet.http.HttpServletRequest;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.math.BigDecimal;
import java.util.UUID;

@RestController
@RequestMapping("/api/internal/market-price")
public class MarketPriceInsightController {

    private static final Logger log = LoggerFactory.getLogger(MarketPriceInsightController.class);
    private static final String INTERNAL_API_KEY_HEADER = "X-Internal-Api-Key";

    private final MarketPriceInsightService insightService;
    private final String internalApiSecret;

    public MarketPriceInsightController(
            MarketPriceInsightService insightService,
            @Value("${INTERNAL_API_SECRET:}") String internalApiSecret
    ) {
        this.insightService = insightService;
        this.internalApiSecret = internalApiSecret;
    }

    @GetMapping("/insight")
    public MarketPriceInsightResponse getInsight(
            HttpServletRequest request,
            @RequestParam(required = false) String q,
            @RequestParam(defaultValue = "MARKET_PRICE") String mode,
            @RequestParam(required = false) UUID tenantId,
            @RequestParam(defaultValue = "USER") String role,
            @RequestParam(required = false) String category,
            @RequestParam(required = false) String material,
            @RequestParam(required = false) BigDecimal inputPrice,
            @RequestParam(required = false) String sourceCode,
            @RequestParam(defaultValue = "5") int limitSamples
    ) {
        if (internalApiSecret != null && !internalApiSecret.isBlank()) {
            String headerKey = request.getHeader(INTERNAL_API_KEY_HEADER);
            if (headerKey == null || !headerKey.trim().equals(internalApiSecret.trim())) {
                log.warn("Internal market-price insight rejected: missing or invalid X-Internal-Api-Key");
                throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Forbidden");
            }
        }

        var req = new MarketPriceInsightService.MarketPriceInsightRequest(
                q, mode, tenantId, role, category, material, inputPrice, sourceCode, limitSamples
        );
        return insightService.getInsight(req);
    }
}
