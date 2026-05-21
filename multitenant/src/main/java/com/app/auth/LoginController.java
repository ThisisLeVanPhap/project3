package com.app.auth;

import com.app.tenants.TenantRepository;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpSession;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@RestController
@RequestMapping("/api/login")
public class LoginController {

    private final TenantMemberRepository tenantMemberRepo;
    private final TenantRepository tenantRepo;
    private final PasswordEncoder passwordEncoder;

    public LoginController(
            TenantMemberRepository tenantMemberRepo,
            TenantRepository tenantRepo,
            PasswordEncoder passwordEncoder
    ) {
        this.tenantMemberRepo = tenantMemberRepo;
        this.tenantRepo = tenantRepo;
        this.passwordEncoder = passwordEncoder;
    }

    @PostMapping({"", "/"})
    public LoginResponse login(@RequestBody LoginRequest req, HttpServletRequest request) {
        String account = req.name() == null ? "" : req.name().trim();
        String password = req.code() == null ? "" : req.code().trim();

        if (account.isBlank() || password.isBlank()) {
            return LoginResponse.fail("Account and password are required");
        }

        LoginResponse tenant = authenticateTenant(account, password, tenantScope(req), request);
        if (tenant.ok()) {
            return tenant;
        }

        LoginResponse admin = authenticateAdmin(account, password, request);
        if (admin.ok()) {
            return admin;
        }

        if (shouldExposeTenantLoginFailure(tenant)) {
            return tenant;
        }

        return LoginResponse.fail("Invalid credentials");
    }

    @PostMapping("/tenant")
    public LoginResponse tenantLogin(@RequestBody LoginRequest req, HttpServletRequest request) {
        String email = req.name() == null ? "" : req.name().trim();
        String password = req.code() == null ? "" : req.code().trim();

        if (email.isBlank() || password.isBlank()) {
            return LoginResponse.fail("Email and password are required");
        }

        return authenticateTenant(email, password, tenantScope(req), request);
    }

    @PostMapping("/admin")
    public LoginResponse adminLogin(@RequestBody LoginRequest req, HttpServletRequest request) {
        String name = req.name() == null ? "" : req.name().trim();
        String password = req.code() == null ? "" : req.code().trim();
        return authenticateAdmin(name, password, request);
    }

    private LoginResponse authenticateTenant(
            String email,
            String password,
            String tenantScope,
            HttpServletRequest request
    ) {
        List<TenantMember> candidates;
        if (!tenantScope.isBlank()) {
            Optional<UUID> tenantId = resolveTenantId(tenantScope);
            if (tenantId.isEmpty()) {
                return LoginResponse.fail("Tenant code not found");
            }
            candidates = tenantMemberRepo.findByTenantIdAndEmailIgnoreCase(tenantId.get(), email)
                    .stream()
                    .toList();
        } else {
            candidates = tenantMemberRepo.findAllByEmailIgnoreCase(email);
        }

        List<TenantMember> matches = candidates.stream()
                .filter(this::isActive)
                .filter(member -> hasPassword(member, password))
                .toList();

        if (matches.size() != 1) {
            return LoginResponse.fail(matches.isEmpty()
                    ? "Invalid tenant member credentials"
                    : "Email belongs to multiple stores. Enter tenant code to choose the correct store.");
        }

        TenantMember member = matches.getFirst();
        AppPrincipal principal = new AppPrincipal(
                member.getId().toString(),
                AppRole.fromDbValue(member.getRole()),
                member.getTenantId().toString(),
                member.getDisplayName() == null || member.getDisplayName().isBlank() ? member.getEmail() : member.getDisplayName(),
                member.getEmail()
        );
        storePrincipal(request, principal);
        return LoginResponse.ok(principal);
    }

    private String tenantScope(LoginRequest req) {
        return req.tenantCode() == null ? "" : req.tenantCode().trim();
    }

    private Optional<UUID> resolveTenantId(String tenantScope) {
        try {
            return tenantRepo.findById(UUID.fromString(tenantScope.trim()))
                    .map(tenant -> tenant.getId());
        } catch (IllegalArgumentException ignored) {
            return tenantRepo.findByCodeIgnoreCase(tenantScope.trim())
                    .map(tenant -> tenant.getId());
        }
    }

    private boolean shouldExposeTenantLoginFailure(LoginResponse response) {
        return "Email belongs to multiple stores. Enter tenant code to choose the correct store."
                .equals(response.message())
                || "Tenant code not found".equals(response.message());
    }

    private LoginResponse authenticateAdmin(String name, String password, HttpServletRequest request) {
        if ("admin".equals(name) && "admin123".equals(password)) {
            AppPrincipal principal = new AppPrincipal(
                    "platform-admin",
                    AppRole.PLATFORM_ADMIN,
                    null,
                    "Platform Admin",
                    "admin"
            );
            storePrincipal(request, principal);
            return LoginResponse.ok(principal);
        }
        return LoginResponse.fail("Invalid admin credentials");
    }

    @PostMapping("/logout")
    public void logout(HttpServletRequest request) {
        HttpSession session = request.getSession(false);
        if (session != null) {
            session.invalidate();
        }
    }

    private void storePrincipal(HttpServletRequest request, AppPrincipal principal) {
        HttpSession session = request.getSession(true);
        session.setAttribute(SessionPrincipalAccessor.SESSION_PRINCIPAL_KEY, principal);
        session.setMaxInactiveInterval((int) java.time.Duration.ofHours(8).getSeconds());
    }

    private boolean isActive(TenantMember member) {
        return member.getStatus() != null && "ACTIVE".equalsIgnoreCase(member.getStatus().trim());
    }

    private boolean hasPassword(TenantMember member, String rawPassword) {
        return member.getPasswordHash() != null
                && !member.getPasswordHash().isBlank()
                && passwordEncoder.matches(rawPassword, member.getPasswordHash());
    }
}
