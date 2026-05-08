package com.app.purchases;

import com.app.auth.AppPrincipal;
import com.app.auth.AppRole;
import com.app.auth.SessionPrincipalAccessor;
import com.app.tenant.TenantContext;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/purchase-requests")
public class PurchaseRequestController {

    private final PurchaseRequestService purchaseRequestService;
    private final SessionPrincipalAccessor principalAccessor;

    public PurchaseRequestController(
            PurchaseRequestService purchaseRequestService,
            SessionPrincipalAccessor principalAccessor
    ) {
        this.purchaseRequestService = purchaseRequestService;
        this.principalAccessor = principalAccessor;
    }

    @GetMapping
    public List<PurchaseRequestResponse> list(
            @RequestParam(value = "tenantId", required = false) String tenantId,
            @RequestParam(value = "status", required = false) String status
    ) {
        principalAccessor.requireTenantOperator();
        String effectiveTenantId = resolveTenantId(tenantId);
        Map<UUID, String> memberDisplayNames = purchaseRequestService.findMemberDisplayNames(effectiveTenantId);

        List<PurchaseRequest> purchaseRequests =
                status == null || status.isBlank()
                        ? purchaseRequestService.findRecentByTenant(effectiveTenantId)
                        : purchaseRequestService.findRecentByTenantAndStatus(effectiveTenantId, status);

        return purchaseRequests
                .stream()
                .map(request -> toResponse(request, memberDisplayNames))
                .toList();
    }

    @PutMapping("/{id}/status")
    public PurchaseRequestResponse updateStatus(
            @PathVariable("id") Long id,
            @RequestBody PurchaseRequestStatusUpdateRequest request
    ) {
        principalAccessor.requireTenantOperator();
        String currentTenantId = resolveTenantId(null);
        PurchaseRequest purchaseRequest = purchaseRequestService.updateStatus(currentTenantId, id, request.status());
        return toResponse(purchaseRequest, purchaseRequestService.findMemberDisplayNames(currentTenantId));
    }

    @PutMapping("/{id}/claim")
    public PurchaseRequestResponse claim(@PathVariable("id") Long id) {
        AppPrincipal principal = principalAccessor.requireTenantOperator();
        String currentTenantId = resolveTenantId(null);
        UUID memberId = requireCurrentMemberId(principal);
        PurchaseRequest purchaseRequest = purchaseRequestService.claim(currentTenantId, id, memberId);
        return toResponse(purchaseRequest, purchaseRequestService.findMemberDisplayNames(currentTenantId));
    }

    @PutMapping("/{id}/assign")
    public PurchaseRequestResponse reassign(
            @PathVariable("id") Long id,
            @RequestBody PurchaseRequestAssignmentRequest request
    ) {
        principalAccessor.requireTenantAdmin();
        String currentTenantId = resolveTenantId(null);
        UUID memberId = parseMemberId(request.memberId());
        PurchaseRequest purchaseRequest = purchaseRequestService.reassign(currentTenantId, id, memberId);
        return toResponse(purchaseRequest, purchaseRequestService.findMemberDisplayNames(currentTenantId));
    }

    private String resolveTenantId(String tenantId) {
        String currentTenantId = TenantContext.get();
        if (currentTenantId == null || currentTenantId.isBlank()) {
            currentTenantId = principalAccessor.requireTenantId();
        }
        if (currentTenantId == null || currentTenantId.isBlank()) {
            throw new IllegalStateException("Missing tenant context");
        }

        String effectiveTenantId = tenantId;
        if (effectiveTenantId == null || effectiveTenantId.isBlank()) {
            effectiveTenantId = currentTenantId;
        } else if (!currentTenantId.equals(effectiveTenantId)) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Tenant filter must match current tenant");
        }
        return effectiveTenantId;
    }

    private PurchaseRequestResponse toResponse(PurchaseRequest purchaseRequest, Map<UUID, String> memberDisplayNames) {
        String assignedToDisplayName = null;
        if (purchaseRequest.getAssignedToMemberId() != null) {
            assignedToDisplayName = memberDisplayNames.getOrDefault(purchaseRequest.getAssignedToMemberId(), null);
        }
        return PurchaseRequestResponse.from(purchaseRequest, assignedToDisplayName);
    }

    private UUID requireCurrentMemberId(AppPrincipal principal) {
        if (principal.role() != AppRole.TENANT_ADMIN && principal.role() != AppRole.TENANT_MEMBER) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Insufficient role");
        }
        return parseMemberId(principal.userId());
    }

    private UUID parseMemberId(String rawMemberId) {
        if (rawMemberId == null || rawMemberId.isBlank()) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Tenant member identity is required");
        }
        try {
            return UUID.fromString(rawMemberId);
        } catch (IllegalArgumentException ex) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Invalid tenant member identity");
        }
    }
}
