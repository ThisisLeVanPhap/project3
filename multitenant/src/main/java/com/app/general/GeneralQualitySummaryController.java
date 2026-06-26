package com.app.general;

import com.app.auth.SessionPrincipalAccessor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/admin/general")
public class GeneralQualitySummaryController {

    private final GeneralQualitySummaryService summaryService;
    private final SessionPrincipalAccessor principalAccessor;

    public GeneralQualitySummaryController(GeneralQualitySummaryService summaryService,
                                            SessionPrincipalAccessor principalAccessor) {
        this.summaryService = summaryService;
        this.principalAccessor = principalAccessor;
    }

    @GetMapping("/quality-summary")
    public GeneralQualitySummaryResponse getQualitySummary(
            @RequestParam(required = false) String sourceCode,
            @RequestParam(required = false) String sourceId
    ) {
        principalAccessor.requirePlatformAdmin();
        return summaryService.getSummary(sourceCode, sourceId);
    }
}
