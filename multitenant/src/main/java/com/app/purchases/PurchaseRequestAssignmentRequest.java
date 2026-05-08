package com.app.purchases;

import com.fasterxml.jackson.annotation.JsonProperty;

public record PurchaseRequestAssignmentRequest(
        @JsonProperty("member_id")
        String memberId
) {
}
