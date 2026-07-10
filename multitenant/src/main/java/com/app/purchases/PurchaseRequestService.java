package com.app.purchases;

import com.app.auth.TenantMember;
import com.app.auth.TenantMemberRepository;
import com.app.chat.Conversation;
import com.app.chat.ConversationRepository;
import com.app.customers.CustomerIdentityService;
import com.app.leads.Lead;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

import static org.springframework.http.HttpStatus.BAD_REQUEST;
import static org.springframework.http.HttpStatus.CONFLICT;
import static org.springframework.http.HttpStatus.FORBIDDEN;
import static org.springframework.http.HttpStatus.NOT_FOUND;

@Slf4j
@Service
public class PurchaseRequestService {

    private static final Pattern PHONE_PATTERN = Pattern.compile("(?<!\\d)(?:\\+?84|0)(?:[\\s.\\-]?\\d){8,10}(?!\\d)");
    private static final Pattern EMAIL_PATTERN = Pattern.compile("(?i)\\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}\\b");
    // Vietnam phone validation after cleaning: digits only (0xxxxxxxxx or 84xxxxxxxxx)
    private static final Pattern PHONE_VALIDATION_PATTERN = Pattern.compile("^(0[3-9]\\d{8}|84[3-9]\\d{8})$");
    private static final Pattern PRODUCT_URL_PATTERN = Pattern.compile("(https?://\\S+)");
    private static final Pattern PRODUCT_LINE_PATTERN = Pattern.compile("(?is)(?:^|\\s)\\d+\\.\\s*([^\\[]+?)\\s*\\[(?:P\\d+)\\]\\s*-\\s*Giá:\\s*([\\d.,]+)\\s*VND.*?SKU:\\s*([A-Z0-9-]+).*?Link nguồn:\\s*(https?://\\S+)");
    private static final Pattern DRAFT_PRODUCT_PATTERN = Pattern.compile("(?is)(?:Sản phẩm|San pham):\\s*(.*?)\\s*-\\s*(?:Số lượng|So luong):\\s*(\\d+).*?(?:Giá tham khảo[^:]*|Gia tham khao[^:]*):\\s*([\\d.]+)(?:.*?(?:Liên hệ|Lien he):\\s*([^\\s]+))?");
    private static final Pattern SKU_PATTERN = Pattern.compile("\\b[A-Z]{2,5}-\\d+\\b");
    private static final List<Pattern> NAME_PATTERNS = List.of(
            Pattern.compile("(?im)^\\s*(?:user:\\s*)?(?:tên|ten|name)\\s*:\\s*([^\\n,.;]{2,80})"),
            Pattern.compile("(?im)\\b(?:tên|ten)\\s+(?:tôi|toi|mình|minh|em|anh|chị|chi|khách|khach)\\s*(?:là|la|:|-)?\\s*([^\\n,.;]{2,80})"),
            Pattern.compile("(?im)\\b(?:họ tên|ho ten|full name|customer name)\\s*(?:là|la|:|-)?\\s*([^\\n,.;]{2,80})"),
            Pattern.compile("(?im)\\b(?:tôi là|toi la|mình là|minh la|em là|em la|anh là|anh la|chị là|chi la)\\s+([^\\n,.;]{2,80})")
    );
    private static final List<Pattern> ADDRESS_PATTERNS = List.of(
            Pattern.compile("(?im)\\b(?:địa chỉ|dia chi|address|giao(?: hàng)? tới|giao(?: hang)? toi|ship(?:ping)?(?: address)?)\\b\\s*(?:(?:nhận hàng|nhan hang)\\s+(?:của tôi|cua toi)\\s+)?(?:là|la|:|-)?\\s*([^\\n]{5,200})"),
            Pattern.compile("(?im)\\b(?:nhận hàng tại|nhan hang tai|ship tới|ship toi)\\b\\s*(?:là|la|:|-)?\\s*([^\\n]{5,200})")
    );
    private static final List<Pattern> NOTES_PATTERNS = List.of(
            Pattern.compile("(?im)\\b(?:ghi chú|ghi chu|note|lưu ý|luu y)\\b\\s*(?:là|la|:|-)?\\s*([^\\n]{3,300})")
    );
    private static final List<String> NAME_KEYS = List.of("customer_name", "full_name", "name");
    private static final List<String> PHONE_KEYS = List.of("phone", "phone_number", "customer_phone");
    private static final List<String> ADDRESS_KEYS = List.of("shipping_address", "delivery_address", "address");
    private static final List<String> NOTES_KEYS = List.of("notes", "note", "customer_note");
    private static final List<String> PRODUCT_KEYS = List.of("requested_product_ref", "product_ref", "product_name", "product_code", "sku", "item");
    private static final List<String> OPEN_STATUSES = List.of(
            PurchaseRequestStatus.NEW.name(),
            PurchaseRequestStatus.PROCESSING.name()
    );

    private final PurchaseRequestRepository purchaseRequestRepo;
    private final TenantMemberRepository tenantMemberRepository;
    private final CustomerIdentityService customerIdentityService;
    private final ConversationRepository conversationRepository;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public PurchaseRequestService(
            PurchaseRequestRepository purchaseRequestRepo,
            TenantMemberRepository tenantMemberRepository
    ) {
        this(purchaseRequestRepo, tenantMemberRepository, null, null);
    }

    @Autowired
    public PurchaseRequestService(
            PurchaseRequestRepository purchaseRequestRepo,
            TenantMemberRepository tenantMemberRepository,
            CustomerIdentityService customerIdentityService,
            ConversationRepository conversationRepository
    ) {
        this.purchaseRequestRepo = purchaseRequestRepo;
        this.tenantMemberRepository = tenantMemberRepository;
        this.customerIdentityService = customerIdentityService;
        this.conversationRepository = conversationRepository;
    }

    public List<PurchaseRequest> findRecentByTenant(String tenantId) {
        return purchaseRequestRepo.findTop200ByTenantIdOrderByCreatedAtDesc(tenantId);
    }

    public List<PurchaseRequest> findRecentByTenantAndStatus(String tenantId, String status) {
        return purchaseRequestRepo.findTop200ByTenantIdAndStatusOrderByCreatedAtDesc(
                tenantId,
                PurchaseRequestStatus.normalize(status)
        );
    }

    public PurchaseRequest findByTenantAndId(String tenantId, Long purchaseRequestId) {
        return requirePurchaseRequest(tenantId, purchaseRequestId);
    }

    public PurchaseRequest updateStatus(String tenantId, Long purchaseRequestId, String status) {
        String normalizedStatus = PurchaseRequestStatus.normalize(status);
        PurchaseRequest purchaseRequest = requirePurchaseRequest(tenantId, purchaseRequestId);

        if (normalizedStatus.equals(purchaseRequest.getStatus())) {
            return purchaseRequest;
        }
        if (PurchaseRequestStatus.PROCESSING.name().equals(normalizedStatus)) {
            requireReadyForProcessing(purchaseRequest);
        }

        purchaseRequest.setStatus(normalizedStatus);
        PurchaseRequest saved = purchaseRequestRepo.save(purchaseRequest);
        log.info("Updated purchase request status id={} tenant={} status={}", saved.getId(), saved.getTenantId(), saved.getStatus());
        return saved;
    }

    public PurchaseRequest updateDetails(String tenantId, Long purchaseRequestId, PurchaseRequestUpdateRequest request) {
        PurchaseRequest purchaseRequest = requirePurchaseRequest(tenantId, purchaseRequestId);

        if (request.customerName() != null && !request.customerName().isBlank()) {
            purchaseRequest.setCustomerName(request.customerName().trim());
        }
        if (request.phone() != null && !request.phone().isBlank()) {
            purchaseRequest.setPhone(request.phone().trim());
        }
        if (request.shippingAddress() != null && !request.shippingAddress().isBlank()) {
            purchaseRequest.setShippingAddress(request.shippingAddress().trim());
        }
        if (request.notes() != null) {
            purchaseRequest.setNotes(request.notes().trim());
        }
        if (request.requestedProductRef() != null) {
            purchaseRequest.setRequestedProductRef(request.requestedProductRef().trim());
        }

        PurchaseRequest saved = purchaseRequestRepo.save(purchaseRequest);
        log.info("Updated purchase request details id={} tenant={}", saved.getId(), saved.getTenantId());
        return saved;
    }

    public PurchaseRequest claim(String tenantId, Long purchaseRequestId, UUID memberId) {
        PurchaseRequest purchaseRequest = requirePurchaseRequest(tenantId, purchaseRequestId);
        TenantMember member = requireTenantMember(tenantId, memberId);

        if (purchaseRequest.getAssignedToMemberId() != null) {
            throw new ResponseStatusException(CONFLICT, "Purchase request is already assigned");
        }

        purchaseRequest.setAssignedToMemberId(member.getId());
        purchaseRequest.setClaimedAt(Instant.now());
        PurchaseRequest saved = purchaseRequestRepo.save(purchaseRequest);
        log.info("Claimed purchase request id={} tenant={} memberId={}", saved.getId(), saved.getTenantId(), member.getId());
        return saved;
    }

    public PurchaseRequest reassign(String tenantId, Long purchaseRequestId, UUID memberId) {
        PurchaseRequest purchaseRequest = requirePurchaseRequest(tenantId, purchaseRequestId);
        TenantMember member = requireTenantMember(tenantId, memberId);

        if (member.getRole() == null || member.getRole().isBlank()) {
            throw new ResponseStatusException(FORBIDDEN, "Tenant member role is required");
        }

        purchaseRequest.setAssignedToMemberId(member.getId());
        if (purchaseRequest.getClaimedAt() == null) {
            purchaseRequest.setClaimedAt(Instant.now());
        }
        PurchaseRequest saved = purchaseRequestRepo.save(purchaseRequest);
        log.info("Reassigned purchase request id={} tenant={} memberId={}", saved.getId(), saved.getTenantId(), member.getId());
        return saved;
    }

    public PurchaseRequest createFromChat(String tenantId, String conversationId, String phone, String customerName, String notes) {
        PurchaseRequest pr = new PurchaseRequest();
        pr.setTenantId(tenantId);
        pr.setChannel("web");
        pr.setConversationId(conversationId);
        pr.setPhone(phone);
        pr.setCustomerName(customerName != null && !customerName.isBlank() ? customerName : "Chat User");
        pr.setNotes(notes);
        pr.setStatus(PurchaseRequestStatus.NEW.name());
        PurchaseRequest saved = purchaseRequestRepo.save(pr);
        log.info("Created purchase request from chat id={} tenant={} conversationId={}", saved.getId(), saved.getTenantId(), conversationId);
        return saved;
    }

    public ChatbotCreateResult createFromChatbotHandoff(ChatbotPurchaseRequestCreateRequest request) {
        String tenantId = required(request.tenantId(), "tenant_id is required");
        parseTenantUuid(tenantId);

        String handoffId = required(request.handoffId(), "handoff_id is required");
        String idempotencyKey = required(request.idempotencyKey(), "idempotency_key is required");
        String phone = normalizeIncomingPhone(required(request.phone(), "phone is required"));
        if (!isValidPhone(phone)) {
            throw new IllegalArgumentException("Invalid phone");
        }

        String requestedProductRef = buildRequestedProductRef(request);
        if (requestedProductRef.isBlank()) {
            throw new IllegalArgumentException("requested_product_ref or product_sku is required");
        }

        Optional<PurchaseRequest> existingByIdempotency =
                purchaseRequestRepo.findByTenantIdAndIdempotencyKey(tenantId, idempotencyKey);
        if (existingByIdempotency.isPresent()) {
            PurchaseRequest existing = existingByIdempotency.get();
            requireCompatibleDuplicate(existing, request, phone, requestedProductRef);
            return new ChatbotCreateResult(existing, false);
        }

        Optional<PurchaseRequest> existingByHandoff =
                purchaseRequestRepo.findByTenantIdAndHandoffId(tenantId, handoffId);
        if (existingByHandoff.isPresent()) {
            throw new ResponseStatusException(CONFLICT, "handoff_id already exists with a different idempotency_key");
        }

        String conversationId = required(request.conversationId(), "conversation_id is required");
        Optional<PurchaseRequest> existingByConversation =
                purchaseRequestRepo.findTop1ByTenantIdAndConversationIdAndStatusInOrderByCreatedAtDesc(
                        tenantId,
                        conversationId,
                        OPEN_STATUSES
                );
        if (existingByConversation.isPresent()) {
            throw new ResponseStatusException(CONFLICT, "conversation_id already has an open purchase request");
        }

        PurchaseRequest created = new PurchaseRequest();
        created.setTenantId(tenantId);
        created.setChannel(defaultIfBlank(request.channel(), "chatbot"));
        created.setConversationId(conversationId);
        created.setCustomerName(defaultIfBlank(request.customerName(), "Chat User"));
        created.setPhone(phone);
        created.setEmail(nullableTrim(request.email()));
        created.setShippingAddress(defaultIfBlank(request.shippingAddress(), ""));
        created.setNotes(defaultIfBlank(request.notes(), ""));
        created.setRequestedProductRef(requestedProductRef);
        created.setHandoffId(handoffId);
        created.setIdempotencyKey(idempotencyKey);
        created.setProductSku(nullableTrim(request.productSku()));
        created.setProductUrl(nullableTrim(request.productUrl()));
        created.setPrice(request.price());
        created.setQuantity(request.quantity());
        created.setStatus(PurchaseRequestStatus.NEW.name());

        PurchaseRequest saved = purchaseRequestRepo.save(created);
        linkCustomerIdentityIfPossible(saved, saved.getCustomerName());
        log.info(
                "Created chatbot purchase request id={} tenant={} handoffId={} idempotencyKey={}",
                saved.getId(),
                saved.getTenantId(),
                saved.getHandoffId(),
                saved.getIdempotencyKey()
        );
        return new ChatbotCreateResult(saved, true);
    }

    public Map<UUID, String> findMemberDisplayNames(String tenantId) {
        UUID tenantUuid = parseTenantUuid(tenantId);
        return tenantMemberRepository.findAllByTenantIdOrderByEmailAsc(tenantUuid)
                .stream()
                .collect(Collectors.toMap(
                        TenantMember::getId,
                        this::displayNameFor,
                        (left, right) -> left,
                        LinkedHashMap::new
                ));
    }

    public PurchaseRequest findOrCreateFromLead(Lead lead) {
        Optional<PurchaseRequest> existingOpt =
                purchaseRequestRepo.findTop1ByTenantIdAndConversationIdAndStatusInOrderByCreatedAtDesc(
                        lead.getTenantId(),
                        lead.getConversationId(),
                        OPEN_STATUSES
                );

        ExtractedPurchaseData extracted = extractFromLead(lead);

        if (existingOpt.isPresent()) {
            PurchaseRequest existing = existingOpt.get();
            boolean changed = mergeInto(existing, lead, extracted);
            if (changed) {
                log.info("Updated purchase request id={} tenant={} conversationId={}", existing.getId(), existing.getTenantId(), existing.getConversationId());
                PurchaseRequest saved = purchaseRequestRepo.save(existing);
                linkCustomerIdentityIfPossible(saved, saved.getCustomerName());
                return saved;
            }
            linkCustomerIdentityIfPossible(existing, existing.getCustomerName());
            return existing;
        }

        PurchaseRequest created = new PurchaseRequest();
        created.setTenantId(lead.getTenantId());
        created.setChannel(defaultString(lead.getChannel()));
        created.setConversationId(defaultString(lead.getConversationId()));
        created.setLeadId(lead.getId());
        created.setCustomerName(extracted.customerName());
        created.setPhone(extracted.phone());
        created.setEmail(nullableTrim(extracted.email()));
        created.setShippingAddress(extracted.shippingAddress());
        created.setNotes(extracted.notes());
        created.setRequestedProductRef(extracted.requestedProductRef());
        created.setProductSku(nullableTrim(extracted.productSku()));
        created.setProductUrl(nullableTrim(extracted.productUrl()));
        created.setPrice(extracted.price());
        created.setQuantity(extracted.quantity());
        created.setStatus(PurchaseRequestStatus.NEW.name());

        PurchaseRequest saved = purchaseRequestRepo.save(created);
        linkCustomerIdentityIfPossible(saved, saved.getCustomerName());
        log.info("Created purchase request id={} tenant={} conversationId={}", saved.getId(), saved.getTenantId(), saved.getConversationId());
        return saved;
    }

    private void linkCustomerIdentityIfPossible(PurchaseRequest purchaseRequest, String displayName) {
        if (customerIdentityService == null || conversationRepository == null || purchaseRequest == null) {
            return;
        }
        if (normalize(purchaseRequest.getPhone()).isBlank() && normalize(purchaseRequest.getEmail()).isBlank()) {
            return;
        }
        UUID tenantUuid;
        UUID conversationUuid;
        try {
            tenantUuid = UUID.fromString(purchaseRequest.getTenantId());
            conversationUuid = UUID.fromString(purchaseRequest.getConversationId());
        } catch (RuntimeException ex) {
            log.debug(
                    "Skip customer identity link because tenant/conversation is not UUID tenant={} conversationId={}",
                    purchaseRequest.getTenantId(),
                    purchaseRequest.getConversationId()
            );
            return;
        }

        Optional<Conversation> conversation = conversationRepository.findById(conversationUuid);
        if (conversation.isEmpty() || !tenantUuid.equals(conversation.get().getTenantId())) {
            return;
        }
        String externalUserId = normalize(conversation.get().getUserExternalId());
        if (externalUserId.isBlank()) {
            return;
        }
        customerIdentityService.resolveOrCreateIdentity(
                tenantUuid,
                purchaseRequest.getChannel(),
                externalUserId,
                displayName,
                purchaseRequest.getPhone(),
                purchaseRequest.getEmail()
        );
    }

    private ExtractedPurchaseData extractFromLead(Lead lead) {
        Map<String, Object> slots = readSlots(lead.getSlotsJson());
        String transcript = defaultString(lead.getTranscript());
        String userTranscript = userOnlyTranscript(transcript);

        String customerName = firstNonBlank(
                slot(slots, NAME_KEYS),
                findByPatterns(userTranscript, NAME_PATTERNS)
        );
        String phone = firstNonBlank(
                slot(slots, PHONE_KEYS),
                findPhone(userTranscript)
        );
        String shippingAddress = firstNonBlank(
                slot(slots, ADDRESS_KEYS),
                findByPatterns(userTranscript, ADDRESS_PATTERNS),
                findFieldValue(userTranscript, "địa chỉ", "dia chi", "address", "giao tới", "giao toi", "ship tới", "ship toi", "nhận hàng tại", "nhan hang tai")
        );
        String notes = firstNonBlank(
                slot(slots, NOTES_KEYS),
                defaultString(lead.getOrderInfo()),
                findByPatterns(userTranscript, NOTES_PATTERNS),
                findFieldValue(userTranscript, "ghi chú", "ghi chu", "note", "lưu ý", "luu y")
        );
        String requestedProductRef = firstNonBlank(
                slot(slots, PRODUCT_KEYS),
                findProductReference(userTranscript)
        );
        ProductCandidate product = combineProductCandidates(
                parseDraftProductCandidate(transcript),
                productCandidateFromSlots(slots),
                parseProductCandidate(firstNonBlank(defaultString(lead.getOrderInfo()), transcript)),
                parseProductCandidate(transcript)
        );
        String email = firstNonBlank(findEmail(userTranscript), product.email());

        return new ExtractedPurchaseData(
                cleanCustomerName(customerName),
                cleanPhone(phone),
                email,
                cleanShippingAddress(shippingAddress),
                normalize(notes),
                cleanRequestedProductRef(firstNonBlank(requestedProductRef, product.name())),
                product.sku(),
                product.url(),
                product.price(),
                product.quantity()
        );
    }

    private Map<String, Object> readSlots(String slotsJson) {
        if (slotsJson == null || slotsJson.isBlank()) {
            return Map.of();
        }
        try {
            return objectMapper.readValue(slotsJson, new TypeReference<LinkedHashMap<String, Object>>() {});
        } catch (Exception ex) {
            log.debug("Failed to parse lead slotsJson for purchase request extraction", ex);
            return Map.of();
        }
    }

    private static boolean mergeInto(PurchaseRequest existing, Lead lead, ExtractedPurchaseData extracted) {
        boolean changed = false;
        changed |= fillIfBlank(existing::getCustomerName, existing::setCustomerName, extracted.customerName());
        changed |= fillIfBlank(existing::getPhone, existing::setPhone, extracted.phone());
        changed |= fillIfBlank(existing::getEmail, existing::setEmail, extracted.email());
        changed |= fillIfBlank(existing::getShippingAddress, existing::setShippingAddress, extracted.shippingAddress());
        changed |= fillIfBlank(existing::getNotes, existing::setNotes, extracted.notes());
        changed |= fillIfBlank(existing::getRequestedProductRef, existing::setRequestedProductRef, extracted.requestedProductRef());
        changed |= fillIfBlank(existing::getProductSku, existing::setProductSku, extracted.productSku());
        changed |= fillIfBlank(existing::getProductUrl, existing::setProductUrl, extracted.productUrl());
        if (existing.getPrice() == null && extracted.price() != null) {
            existing.setPrice(extracted.price());
            changed = true;
        }
        if (existing.getQuantity() == null && extracted.quantity() != null) {
            existing.setQuantity(extracted.quantity());
            changed = true;
        }
        if (existing.getLeadId() == null && lead.getId() != null) {
            existing.setLeadId(lead.getId());
            changed = true;
        }
        return changed;
    }

    private static boolean fillIfBlank(ValueSupplier getter, ValueConsumer setter, String candidate) {
        if (!normalize(getter.get()).isBlank() || normalize(candidate).isBlank()) {
            return false;
        }
        setter.accept(candidate);
        return true;
    }

    private static String slot(Map<String, Object> slots, List<String> keys) {
        for (String key : keys) {
            Object value = slots.get(key);
            if (value != null && !String.valueOf(value).isBlank()) {
                return String.valueOf(value);
            }
        }
        return "";
    }

    private static String findPhone(String transcript) {
        Matcher matcher = PHONE_PATTERN.matcher(transcript);
        if (!matcher.find()) {
            return "";
        }
        return matcher.group().replaceAll("[^\\d+]", "");
    }

    private static String findEmail(String transcript) {
        Matcher matcher = EMAIL_PATTERN.matcher(transcript);
        return matcher.find() ? matcher.group() : "";
    }

    private static String findProductReference(String transcript) {
        for (String line : transcript.split("\\R")) {
            if (!isUserLine(line)) {
                continue;
            }
            String normalizedLine = stripRolePrefix(normalize(line));
            Matcher urlMatcher = PRODUCT_URL_PATTERN.matcher(normalizedLine);
            if (urlMatcher.find()) {
                return urlMatcher.group(1);
            }
            String lower = normalizedLine.toLowerCase(Locale.ROOT);
            if (lower.contains("sản phẩm muốn mua")
                    || lower.contains("san pham muon mua")
                    || lower.contains("mã sản phẩm")
                    || lower.contains("ma san pham")
                    || lower.contains("product code")
                    || lower.contains("sku")) {
                return normalizedLine;
            }
        }
        return "";
    }

    private static String findFieldValue(String transcript, String... keywords) {
        for (String line : transcript.split("\\R")) {
            String normalizedLine = stripRolePrefix(normalize(line));
            String lower = normalizedLine.toLowerCase(Locale.ROOT);
            for (String keyword : keywords) {
                String normalizedKeyword = keyword.toLowerCase(Locale.ROOT);
                if (!lower.contains(normalizedKeyword)) {
                    continue;
                }
                int colonIndex = normalizedLine.indexOf(':');
                if (colonIndex >= 0 && colonIndex + 1 < normalizedLine.length()) {
                    return normalize(normalizedLine.substring(colonIndex + 1));
                }
                int keywordIndex = lower.indexOf(normalizedKeyword);
                if (keywordIndex >= 0) {
                    String remainder = normalize(normalizedLine.substring(keywordIndex + normalizedKeyword.length()));
                    remainder = remainder.replaceFirst("^(là|la|is)\\s+", "");
                    if (!remainder.isBlank()) {
                        return remainder;
                    }
                }
            }
        }
        return "";
    }

    private static void requireReadyForProcessing(PurchaseRequest purchaseRequest) {
        String customerName = normalize(purchaseRequest.getCustomerName());
        String phone = normalize(purchaseRequest.getPhone());
        String shippingAddress = normalize(purchaseRequest.getShippingAddress());
        if (customerName.isBlank() || phone.isBlank() || shippingAddress.isBlank()) {
            throw new ResponseStatusException(
                    BAD_REQUEST,
                    "Purchase request requires customer name, phone, and shipping address before processing"
            );
        }
        if (!isValidPhone(phone)) {
            throw new ResponseStatusException(
                    BAD_REQUEST,
                    "Purchase request phone is invalid before processing. Use a Vietnam mobile number like 09xxxxxxxx or 84xxxxxxxxx"
            );
        }
    }

    private static String userOnlyTranscript(String transcript) {
        StringBuilder builder = new StringBuilder();
        for (String line : transcript.split("\\R")) {
            if (isUserLine(line)) {
                builder.append(line).append('\n');
            }
        }
        return builder.toString();
    }

    private static boolean isUserLine(String line) {
        String normalized = normalize(line).toLowerCase(Locale.ROOT);
        return normalized.isBlank() || normalized.startsWith("user:");
    }

    private static String stripRolePrefix(String line) {
        return line.replaceFirst("^(user|assistant|system)\\s*:\\s*", "");
    }

    private static String findByPatterns(String transcript, List<Pattern> patterns) {
        for (Pattern pattern : patterns) {
            Matcher matcher = pattern.matcher(transcript);
            if (matcher.find()) {
                return matcher.group(1);
            }
        }
        return "";
    }

    private static String firstNonBlank(String... values) {
        for (String value : values) {
            String normalized = normalize(value);
            if (!normalized.isBlank()) {
                return normalized;
            }
        }
        return "";
    }

    private static String defaultString(String value) {
        return value == null ? "" : value;
    }

    private static String normalize(String value) {
        return value == null ? "" : value.replaceAll("\\s{2,}", " ").trim();
    }

    private static String cleanCustomerName(String value) {
        String cleaned = normalize(value);
        if (cleaned.matches("(?i)[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")) {
            return "";
        }
        String lower = cleaned.toLowerCase(Locale.ROOT);
        if (lower.matches(".*\\b(ghs|gho|sku|mẫu|mau|sofa|bàn|ban|ghế|ghe|đèn|den|sản phẩm|san pham)\\b.*")) {
            return "";
        }
        if (cleaned.matches(".*\\d.*")) {
            return "";
        }
        return cleaned;
    }

    private static String cleanPhone(String value) {
        return normalize(value).replaceAll("[^\\d+]", "");
    }

    private static String normalizeIncomingPhone(String value) {
        return cleanPhone(value).replaceFirst("^\\+84", "84");
    }

    private static boolean isValidPhone(String cleanedPhone) {
        return PHONE_VALIDATION_PATTERN.matcher(cleanedPhone).matches();
    }

    private static String cleanShippingAddress(String value) {
        String cleaned = normalize(value);
        cleaned = cleaned.replaceFirst("(?i)[,.;!?]?\\s*(hay|hãy|vui lòng|vui long|xin|làm ơn|lam on|nhờ)\\b.*$", "");
        cleaned = cleaned.replaceFirst("(?i)[,.;!?]?\\s*(xác nhận|xac nhan|yêu cầu mua hàng|yeu cau mua hang)\\b.*$", "");
        return normalize(cleaned).replaceAll("[,.;!?]+$", "");
    }

    private static String cleanRequestedProductRef(String value) {
        String cleaned = normalize(value);
        if (cleaned.toLowerCase(Locale.ROOT).startsWith("assistant:")) {
            return "";
        }
        return cleaned;
    }

    private static ProductCandidate parseProductCandidate(String text) {
        String normalized = normalize(text);
        if (normalized.isBlank()) {
            return ProductCandidate.empty();
        }
        Matcher matcher = PRODUCT_LINE_PATTERN.matcher(normalized);
        if (!matcher.find()) {
            return ProductCandidate.empty();
        }
        return new ProductCandidate(
                normalize(matcher.group(1)),
                normalize(matcher.group(3)),
                normalize(matcher.group(4)),
                parsePrice(matcher.group(2)),
                1,
                ""
        );
    }

    private static ProductCandidate parseDraftProductCandidate(String text) {
        String normalized = normalize(text.replaceAll("(?im)^\\s*(?:user|assistant):\\s*", ""));
        if (normalized.isBlank()) {
            return ProductCandidate.empty();
        }
        Matcher matcher = DRAFT_PRODUCT_PATTERN.matcher(normalized);
        ProductCandidate latest = ProductCandidate.empty();
        while (matcher.find()) {
            String name = normalize(matcher.group(1)).replaceFirst("^[-\\s]+", "");
            latest = new ProductCandidate(
                    name,
                    extractSku(name),
                    "",
                    parsePrice(matcher.group(3)),
                    parseQuantity(matcher.group(2)),
                    normalize(matcher.group(4))
            );
        }
        return latest;
    }

    @SuppressWarnings("unchecked")
    private static ProductCandidate productCandidateFromSlots(Map<String, Object> slots) {
        Object debug = slots.get("debug");
        if (!(debug instanceof Map<?, ?> debugMap)) {
            return ProductCandidate.empty();
        }
        Object selectedProducts = debugMap.get("selected_products");
        if (selectedProducts instanceof List<?> products && !products.isEmpty() && products.get(0) instanceof Map<?, ?> product) {
            return new ProductCandidate(
                    normalize(stringValue(product, "product_name")),
                    normalize(stringValue(product, "sku")),
                    normalize(stringValue(product, "source_url")),
                    parsePrice(product.get("price")),
                    1,
                    ""
            );
        }
        Object knownSlots = debugMap.get("known_slots");
        if (knownSlots instanceof Map<?, ?> known) {
            String name = normalize(stringValue(known, "selected_product_name"));
            String sku = normalize(stringValue(known, "selected_product_id"));
            if (!name.isBlank() || !sku.isBlank()) {
                return new ProductCandidate(name, sku, "", null, 1, "");
            }
        }
        return ProductCandidate.empty();
    }

    private static String stringValue(Map<?, ?> map, String key) {
        Object value = map.get(key);
        return value == null ? "" : String.valueOf(value);
    }

    private static ProductCandidate combineProductCandidates(ProductCandidate... candidates) {
        String name = "";
        String sku = "";
        String url = "";
        BigDecimal price = null;
        Integer quantity = null;
        String email = "";
        for (ProductCandidate candidate : candidates) {
            if (candidate != null && candidate.hasAnyValue()) {
                if (name.isBlank()) name = normalize(candidate.name());
                if (sku.isBlank()) sku = normalize(candidate.sku());
                if (url.isBlank() && sameSkuOrMissing(sku, candidate.sku())) url = normalize(candidate.url());
                if (price == null && sameSkuOrMissing(sku, candidate.sku())) price = candidate.price();
                if (quantity == null && sameSkuOrMissing(sku, candidate.sku())) quantity = candidate.quantity();
                if (email.isBlank()) email = normalize(candidate.email());
            }
        }
        return new ProductCandidate(name, sku, url, price, quantity, email);
    }

    private static boolean sameSkuOrMissing(String selectedSku, String candidateSku) {
        String selected = normalize(selectedSku);
        String candidate = normalize(candidateSku);
        return selected.isBlank() || candidate.isBlank() || selected.equalsIgnoreCase(candidate);
    }

    private static BigDecimal parsePrice(Object value) {
        if (value == null) {
            return null;
        }
        String raw = String.valueOf(value).replaceAll("[^0-9.]", "");
        if (raw.isBlank()) {
            return null;
        }
        int firstDot = raw.indexOf('.');
        if (firstDot >= 0 && raw.indexOf('.', firstDot + 1) >= 0) {
            raw = raw.replace(".", "");
        }
        try {
            return new BigDecimal(raw);
        } catch (NumberFormatException ex) {
            return null;
        }
    }

    private static Integer parseQuantity(String value) {
        String normalized = normalize(value).replaceAll("[^0-9]", "");
        if (normalized.isBlank()) {
            return null;
        }
        try {
            return Integer.parseInt(normalized);
        } catch (NumberFormatException ex) {
            return null;
        }
    }

    private static String extractSku(String value) {
        Matcher matcher = SKU_PATTERN.matcher(normalize(value));
        return matcher.find() ? matcher.group() : "";
    }

    private PurchaseRequest requirePurchaseRequest(String tenantId, Long purchaseRequestId) {
        return purchaseRequestRepo.findByIdAndTenantId(purchaseRequestId, tenantId)
                .orElseThrow(() -> new ResponseStatusException(NOT_FOUND, "Purchase request not found"));
    }

    private TenantMember requireTenantMember(String tenantId, UUID memberId) {
        UUID tenantUuid = parseTenantUuid(tenantId);
        return tenantMemberRepository.findByIdAndTenantId(memberId, tenantUuid)
                .orElseThrow(() -> new ResponseStatusException(NOT_FOUND, "Tenant member not found"));
    }

    private UUID parseTenantUuid(String tenantId) {
        try {
            return UUID.fromString(tenantId);
        } catch (IllegalArgumentException ex) {
            throw new ResponseStatusException(FORBIDDEN, "Invalid tenant scope");
        }
    }

    private String displayNameFor(TenantMember member) {
        if (member.getDisplayName() != null && !member.getDisplayName().isBlank()) {
            return member.getDisplayName().trim();
        }
        return member.getEmail() == null ? "" : member.getEmail().trim();
    }

    private static String required(String value, String message) {
        String normalized = normalize(value);
        if (normalized.isBlank()) {
            throw new IllegalArgumentException(message);
        }
        return normalized;
    }

    private static String nullableTrim(String value) {
        String normalized = normalize(value);
        return normalized.isBlank() ? null : normalized;
    }

    private static String defaultIfBlank(String value, String fallback) {
        String normalized = normalize(value);
        return normalized.isBlank() ? fallback : normalized;
    }

    private static String buildRequestedProductRef(ChatbotPurchaseRequestCreateRequest request) {
        String requestedProductRef = normalize(request.requestedProductRef());
        if (!requestedProductRef.isBlank()) {
            return requestedProductRef;
        }

        String productSku = normalize(request.productSku());
        String productUrl = normalize(request.productUrl());
        if (!productSku.isBlank() && !productUrl.isBlank()) {
            return productSku + " - " + productUrl;
        }
        return firstNonBlank(productSku, productUrl);
    }

    private static void requireCompatibleDuplicate(
            PurchaseRequest existing,
            ChatbotPurchaseRequestCreateRequest request,
            String phone,
            String requestedProductRef
    ) {
        requireSame("handoff_id", existing.getHandoffId(), request.handoffId());
        requireSame("phone", existing.getPhone(), phone);
        requireSame("requested_product_ref", existing.getRequestedProductRef(), requestedProductRef);
        requireSame("product_sku", existing.getProductSku(), request.productSku());
        requireSame("product_url", existing.getProductUrl(), request.productUrl());
        requireSame("email", existing.getEmail(), request.email());
        requireSame("price", existing.getPrice(), request.price());
        requireSame("quantity", existing.getQuantity(), request.quantity());
    }

    private static void requireSame(String field, String existingValue, String incomingValue) {
        String existing = normalize(existingValue);
        String incoming = normalize(incomingValue);
        if (!incoming.isBlank() && !existing.equals(incoming)) {
            throw new ResponseStatusException(CONFLICT, "Conflicting duplicate payload field: " + field);
        }
    }

    private static void requireSame(String field, BigDecimal existingValue, BigDecimal incomingValue) {
        if (incomingValue != null && existingValue != null && existingValue.compareTo(incomingValue) != 0) {
            throw new ResponseStatusException(CONFLICT, "Conflicting duplicate payload field: " + field);
        }
        if (incomingValue != null && existingValue == null) {
            throw new ResponseStatusException(CONFLICT, "Conflicting duplicate payload field: " + field);
        }
    }

    private static void requireSame(String field, Integer existingValue, Integer incomingValue) {
        if (incomingValue != null && !incomingValue.equals(existingValue)) {
            throw new ResponseStatusException(CONFLICT, "Conflicting duplicate payload field: " + field);
        }
    }

    public record ChatbotCreateResult(PurchaseRequest purchaseRequest, boolean created) {
    }

    private record ExtractedPurchaseData(
            String customerName,
            String phone,
            String email,
            String shippingAddress,
            String notes,
            String requestedProductRef,
            String productSku,
            String productUrl,
            BigDecimal price,
            Integer quantity
    ) {
    }

    private record ProductCandidate(
            String name,
            String sku,
            String url,
            BigDecimal price,
            Integer quantity,
            String email
    ) {
        private static ProductCandidate empty() {
            return new ProductCandidate("", "", "", null, null, "");
        }

        private boolean hasAnyValue() {
            return !normalize(name).isBlank()
                    || !normalize(sku).isBlank()
                    || !normalize(url).isBlank()
                    || price != null
                    || quantity != null
                    || !normalize(email).isBlank();
        }
    }

    @FunctionalInterface
    private interface ValueSupplier {
        String get();
    }

    @FunctionalInterface
    private interface ValueConsumer {
        void accept(String value);
    }
}
