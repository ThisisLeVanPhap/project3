package com.app.modelserver;

public enum UpstreamFailureCategory {
    UNAVAILABLE,
    TIMEOUT,
    UPSTREAM_4XX,
    UPSTREAM_5XX
}
