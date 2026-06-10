package com.app.leads;

import java.time.Instant;

public record LeadActivityDto(
        String type,
        String label,
        Instant timestamp,
        String details
) {}
