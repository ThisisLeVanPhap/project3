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
@RequestMapping("/api/internal/general-products")
public class GeneralProductSearchController {

    private static final Logger log = LoggerFactory.getLogger(GeneralProductSearchController.class);
    private static final String INTERNAL_API_KEY_HEADER = "X-Internal-Api-Key";

    private final GeneralProductSearchService searchService;
    private final String internalApiSecret;

    public GeneralProductSearchController(
            GeneralProductSearchService searchService,
            @Value("${INTERNAL_API_SECRET:}") String internalApiSecret
    ) {
        this.searchService = searchService;
        this.internalApiSecret = internalApiSecret;
    }

    @GetMapping("/search")
    public GeneralProductSearchResult search(
            HttpServletRequest request,
            @RequestParam String q,
            @RequestParam(defaultValue = "GENERAL_COMPARE") String mode,
            @RequestParam(required = false) UUID tenantId,
            @RequestParam(required = false) String role,
            @RequestParam(required = false) String category,
            @RequestParam(required = false) String material,
            @RequestParam(required = false) BigDecimal minPrice,
            @RequestParam(required = false) BigDecimal maxPrice,
            @RequestParam(required = false) String sourceCode,
            @RequestParam(defaultValue = "5") int limit,
            @RequestParam(defaultValue = "0") int offset
    ) {
        // Internal API key check
        if (internalApiSecret != null && !internalApiSecret.isBlank()) {
            String headerKey = request.getHeader(INTERNAL_API_KEY_HEADER);
            if (headerKey == null || !headerKey.trim().equals(internalApiSecret.trim())) {
                log.warn("Internal API search rejected: missing or invalid X-Internal-Api-Key (secret configured)");
                throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Forbidden");
            }
        }

        SearchCriteria criteria = new SearchCriteria(
                q, mode, tenantId, role,
                category, material, minPrice, maxPrice,
                sourceCode, limit, offset
        );
        return searchService.search(criteria);
    }
}
