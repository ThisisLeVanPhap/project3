package com.app.leads;

import jakarta.persistence.*;
import java.time.Instant;

@Entity
@Table(name = "leads")
public class Lead {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String tenantId;
    private String channel;          // messenger / telegram / web
    private String conversationId;

    private String customerHandle;   // psid or telegram chat id or username
    private String status;           // NEW / CONTACTED / CLOSED

    @Column(length = 4000)
    private String slotsJson;        // snapshot of slots from Python

    @Column(length = 12000)
    private String transcript;       // last N messages

    @Column(length = 12000)
    private String orderInfo;        // delivery info collected by staff

    private String shippingStatus;   // NEW / READY / SHIPPED

    private Instant createdAt;

    public Lead() {}

    public static Lead createNew(String tenantId, String channel, String conversationId,
                                 String customerHandle, String slotsJson, String transcript) {
        Lead l = new Lead();
        l.tenantId = tenantId;
        l.channel = channel;
        l.conversationId = conversationId;
        l.customerHandle = customerHandle;
        l.slotsJson = slotsJson;
        l.transcript = transcript;
        l.status = "NEW";
        l.shippingStatus = "NEW";
        l.createdAt = Instant.now();
        return l;
    }

    // getters/setters
    public Long getId() { return id; }
    public String getTenantId() { return tenantId; }
    public String getChannel() { return channel; }
    public String getConversationId() { return conversationId; }
    public String getCustomerHandle() { return customerHandle; }
    public String getStatus() { return status; }
    public String getSlotsJson() { return slotsJson; }
    public String getTranscript() { return transcript; }
    public String getOrderInfo() { return orderInfo; }
    public String getShippingStatus() { return shippingStatus; }
    public Instant getCreatedAt() { return createdAt; }

    public void setStatus(String status) { this.status = status; }
    public void setOrderInfo(String s) { this.orderInfo = s; }
    public void setShippingStatus(String s) { this.shippingStatus = s; }
}
