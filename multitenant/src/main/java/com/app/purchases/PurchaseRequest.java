package com.app.purchases;

import jakarta.persistence.*;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(
        name = "purchase_requests",
        uniqueConstraints = @UniqueConstraint(name = "uq_purchase_request_tenant_conversation", columnNames = {"tenant_id", "conversation_id"})
)
public class PurchaseRequest {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "tenant_id", nullable = false, length = 64)
    private String tenantId;

    @Column(nullable = false, length = 32)
    private String channel;

    @Column(name = "conversation_id", nullable = false, length = 128)
    private String conversationId;

    @Column(name = "lead_id")
    private Long leadId;

    @Column(name = "customer_name", nullable = false, length = 255)
    private String customerName = "";

    @Column(nullable = false, length = 64)
    private String phone = "";

    @Column(name = "shipping_address", nullable = false, length = 2000)
    private String shippingAddress = "";

    @Column(nullable = false, length = 4000)
    private String notes = "";

    @Column(nullable = false, length = 32)
    private String status = "NEW";

    @Column(name = "requested_product_ref", length = 512)
    private String requestedProductRef = "";

    @Column(name = "handoff_id", length = 128)
    private String handoffId;

    @Column(name = "idempotency_key", length = 256)
    private String idempotencyKey;

    @Column(name = "product_sku", length = 128)
    private String productSku;

    @Column(name = "product_url", length = 1000)
    private String productUrl;

    @Column(name = "price", precision = 19, scale = 2)
    private BigDecimal price;

    @Column(name = "quantity")
    private Integer quantity;

    @Column(name = "email", length = 255)
    private String email;

    @Column(name = "assigned_to_member_id")
    private UUID assignedToMemberId;

    @Column(name = "claimed_at")
    private Instant claimedAt;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt = Instant.now();

    @Column(name = "updated_at")
    private Instant updatedAt;

    public Long getId() {
        return id;
    }

    public String getTenantId() {
        return tenantId;
    }

    public void setTenantId(String tenantId) {
        this.tenantId = tenantId;
    }

    public String getChannel() {
        return channel;
    }

    public void setChannel(String channel) {
        this.channel = channel;
    }

    public String getConversationId() {
        return conversationId;
    }

    public void setConversationId(String conversationId) {
        this.conversationId = conversationId;
    }

    public Long getLeadId() {
        return leadId;
    }

    public void setLeadId(Long leadId) {
        this.leadId = leadId;
    }

    public String getCustomerName() {
        return customerName;
    }

    public void setCustomerName(String customerName) {
        this.customerName = customerName;
    }

    public String getPhone() {
        return phone;
    }

    public void setPhone(String phone) {
        this.phone = phone;
    }

    public String getShippingAddress() {
        return shippingAddress;
    }

    public void setShippingAddress(String shippingAddress) {
        this.shippingAddress = shippingAddress;
    }

    public String getNotes() {
        return notes;
    }

    public void setNotes(String notes) {
        this.notes = notes;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = PurchaseRequestStatus.normalize(status);
    }

    public String getRequestedProductRef() {
        return requestedProductRef;
    }

    public void setRequestedProductRef(String requestedProductRef) {
        this.requestedProductRef = requestedProductRef;
    }

    public String getHandoffId() {
        return handoffId;
    }

    public void setHandoffId(String handoffId) {
        this.handoffId = handoffId;
    }

    public String getIdempotencyKey() {
        return idempotencyKey;
    }

    public void setIdempotencyKey(String idempotencyKey) {
        this.idempotencyKey = idempotencyKey;
    }

    public String getProductSku() {
        return productSku;
    }

    public void setProductSku(String productSku) {
        this.productSku = productSku;
    }

    public String getProductUrl() {
        return productUrl;
    }

    public void setProductUrl(String productUrl) {
        this.productUrl = productUrl;
    }

    public BigDecimal getPrice() {
        return price;
    }

    public void setPrice(BigDecimal price) {
        this.price = price;
    }

    public Integer getQuantity() {
        return quantity;
    }

    public void setQuantity(Integer quantity) {
        this.quantity = quantity;
    }

    public String getEmail() {
        return email;
    }

    public void setEmail(String email) {
        this.email = email;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }

    public UUID getAssignedToMemberId() {
        return assignedToMemberId;
    }

    public void setAssignedToMemberId(UUID assignedToMemberId) {
        this.assignedToMemberId = assignedToMemberId;
    }

    public Instant getClaimedAt() {
        return claimedAt;
    }

    public void setClaimedAt(Instant claimedAt) {
        this.claimedAt = claimedAt;
    }

    @PrePersist
    void prePersist() {
        if (createdAt == null) {
            createdAt = Instant.now();
        }
        customerName = safe(customerName);
        phone = safe(phone);
        shippingAddress = safe(shippingAddress);
        notes = safe(notes);
        requestedProductRef = safe(requestedProductRef);
        handoffId = nullableSafe(handoffId);
        idempotencyKey = nullableSafe(idempotencyKey);
        productSku = nullableSafe(productSku);
        productUrl = nullableSafe(productUrl);
        email = nullableSafe(email);
        status = safe(status).isBlank() ? PurchaseRequestStatus.NEW.name() : PurchaseRequestStatus.normalize(status);
    }

    @PreUpdate
    void preUpdate() {
        updatedAt = Instant.now();
        customerName = safe(customerName);
        phone = safe(phone);
        shippingAddress = safe(shippingAddress);
        notes = safe(notes);
        requestedProductRef = safe(requestedProductRef);
        handoffId = nullableSafe(handoffId);
        idempotencyKey = nullableSafe(idempotencyKey);
        productSku = nullableSafe(productSku);
        productUrl = nullableSafe(productUrl);
        email = nullableSafe(email);
        status = safe(status).isBlank() ? PurchaseRequestStatus.NEW.name() : PurchaseRequestStatus.normalize(status);
    }

    private static String safe(String value) {
        return value == null ? "" : value.trim();
    }

    private static String nullableSafe(String value) {
        if (value == null) {
            return null;
        }
        String trimmed = value.trim();
        return trimmed.isBlank() ? null : trimmed;
    }
}
