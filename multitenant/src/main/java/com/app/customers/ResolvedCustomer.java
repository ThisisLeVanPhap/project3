package com.app.customers;

public record ResolvedCustomer(
        UnifiedCustomer unifiedCustomer,
        CustomerIdentity identity,
        boolean createdCustomer,
        boolean createdIdentity,
        boolean linkedByStrongIdentifier,
        String warning
) {
}
