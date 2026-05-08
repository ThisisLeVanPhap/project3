package com.app.admin;

import com.app.auth.SessionPrincipalAccessor;
import com.app.chat.MessageRepository;
import com.app.feedback.FeedbackRepository;
import com.app.leads.LeadRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.*;

@RestController
@RequestMapping("/admin/api/stats")
@RequiredArgsConstructor
public class AdminStatsController {

    private final MessageRepository msgRepo;
    private final LeadRepository leadRepo;
    private final FeedbackRepository feedbackRepo;
    private final SessionPrincipalAccessor principalAccessor;

    record Overview(
            long totalConversations,
            long totalLeads,
            double leadConversionRate,
            double shippedRate,
            double feedbackPositiveRate,
            Map<String, Long> leadStatusBreakdown
    ) {}

    record TenantRow(
            String tenantId,
            long conversations,
            long leads,
            long contacted,
            long shipped,
            double feedbackPosRate
    ) {}

    record DayRow(
            String day,
            long leadsCreated,
            long shipped,
            long feedbackGood,
            long feedbackBad
    ) {}

    @GetMapping("/overview")
    public Overview overview(@RequestParam(defaultValue = "7") int days) {
        principalAccessor.requirePlatformAdmin();
        Instant since = Instant.now().minus(days, ChronoUnit.DAYS);

        long conv = msgRepo.countDistinctConversationsSince(since);
        long leads = leadRepo.countAllSince(since);
        long shipped = leadRepo.countShippedSince(since);

        long fbTotal = feedbackRepo.countAllSince(since);
        long fbGood = feedbackRepo.countGoodSince(since);

        double convRate = conv == 0 ? 0.0 : (leads * 1.0 / conv);
        double shippedRate = leads == 0 ? 0.0 : (shipped * 1.0 / leads);
        double posRate = fbTotal == 0 ? 0.0 : (fbGood * 1.0 / fbTotal);

        Map<String, Long> breakdown = new LinkedHashMap<>();
        for (Object[] row : leadRepo.statusBreakdownSince(since)) {
            breakdown.put(String.valueOf(row[0]), ((Number) row[1]).longValue());
        }

        return new Overview(conv, leads, convRate, shippedRate, posRate, breakdown);
    }

    @GetMapping("/by-tenant")
    public List<TenantRow> byTenant(@RequestParam(defaultValue = "30") int days) {
        principalAccessor.requirePlatformAdmin();
        Instant since = Instant.now().minus(days, ChronoUnit.DAYS);

        Map<String, Long> convByTenant = toMap(msgRepo.conversationsByTenantSince(since));
        Map<String, Long> leadsByTenant = toMap(leadRepo.leadsByTenantSince(since));
        Map<String, Long> shippedByTenant = toMap(leadRepo.shippedByTenantSince(since));
        Map<String, Long> contactedByTenant = toMap(leadRepo.contactedByTenantSince(since));

        Map<String, double[]> fb = new HashMap<>();
        for (Object[] r : feedbackRepo.posRateByTenantSince(since)) {
            String tid = String.valueOf(r[0]);
            long good = r[1] == null ? 0 : ((Number) r[1]).longValue();
            long total = r[2] == null ? 0 : ((Number) r[2]).longValue();
            fb.put(tid, new double[]{good, total});
        }

        Set<String> tids = new TreeSet<>();
        tids.addAll(convByTenant.keySet());
        tids.addAll(leadsByTenant.keySet());
        tids.addAll(shippedByTenant.keySet());
        tids.addAll(contactedByTenant.keySet());
        tids.addAll(fb.keySet());

        List<TenantRow> out = new ArrayList<>();
        for (String tid : tids) {
            long c = convByTenant.getOrDefault(tid, 0L);
            long l = leadsByTenant.getOrDefault(tid, 0L);
            long s = shippedByTenant.getOrDefault(tid, 0L);
            long ct = contactedByTenant.getOrDefault(tid, 0L);

            double[] arr = fb.getOrDefault(tid, new double[]{0, 0});
            double pos = arr[1] == 0 ? 0.0 : (arr[0] / arr[1]);

            out.add(new TenantRow(tid, c, l, ct, s, pos));
        }

        out.sort((a, b) -> Long.compare(b.leads(), a.leads()));
        return out;
    }

    @GetMapping("/timeseries")
    public List<DayRow> timeseries(@RequestParam(defaultValue = "30") int days) {
        principalAccessor.requirePlatformAdmin();
        List<DayRow> rows = new ArrayList<>();

        Instant today = Instant.now().truncatedTo(ChronoUnit.DAYS);
        for (int i = days - 1; i >= 0; i--) {
            Instant dayStart = today.minus(i, ChronoUnit.DAYS);
            Instant dayEnd = dayStart.plus(1, ChronoUnit.DAYS);

            long leadsCreated = countLeadsBetween(dayStart, dayEnd);
            long shipped = countShippedBetween(dayStart, dayEnd);
            long good = countFeedbackBetween(dayStart, dayEnd, 1);
            long bad = countFeedbackBetween(dayStart, dayEnd, -1);

            rows.add(new DayRow(dayStart.toString().substring(0, 10), leadsCreated, shipped, good, bad));
        }
        return rows;
    }

    private Map<String, Long> toMap(List<Object[]> rows) {
        Map<String, Long> m = new HashMap<>();
        for (Object[] r : rows) {
            m.put(String.valueOf(r[0]), ((Number) r[1]).longValue());
        }
        return m;
    }

    private long countLeadsBetween(Instant a, Instant b) {
        return leadRepo.findAll().stream()
                .filter(l -> l.getCreatedAt() != null && !l.getCreatedAt().isBefore(a) && l.getCreatedAt().isBefore(b))
                .count();
    }

    private long countShippedBetween(Instant a, Instant b) {
        return leadRepo.findAll().stream()
                .filter(l -> l.getCreatedAt() != null && !l.getCreatedAt().isBefore(a) && l.getCreatedAt().isBefore(b))
                .filter(l -> "SHIPPED".equalsIgnoreCase(l.getShippingStatus()))
                .count();
    }

    private long countFeedbackBetween(Instant a, Instant b, int rating) {
        return feedbackRepo.findAll().stream()
                .filter(f -> f.getCreatedAt() != null && !f.getCreatedAt().isBefore(a) && f.getCreatedAt().isBefore(b))
                .filter(f -> f.getRating() == rating)
                .count();
    }
}
