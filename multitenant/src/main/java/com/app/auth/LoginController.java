package com.app.auth;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpSession;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/login")
public class LoginController {

    private final TenantMemberRepository tenantMemberRepo;
    private final PasswordEncoder passwordEncoder;

    public LoginController(TenantMemberRepository tenantMemberRepo, PasswordEncoder passwordEncoder) {
        this.tenantMemberRepo = tenantMemberRepo;
        this.passwordEncoder = passwordEncoder;
    }

    @PostMapping("/tenant")
    public LoginResponse tenantLogin(@RequestBody LoginRequest req, HttpServletRequest request) {
        String email = req.name() == null ? "" : req.name().trim();
        String password = req.code() == null ? "" : req.code().trim();

        if (email.isBlank() || password.isBlank()) {
            return LoginResponse.fail("Email and password are required");
        }

        List<TenantMember> matches = tenantMemberRepo.findAllByEmailIgnoreCase(email)
                .stream()
                .filter(this::isActive)
                .filter(member -> hasPassword(member, password))
                .toList();

        if (matches.size() != 1) {
            return LoginResponse.fail(matches.isEmpty()
                    ? "Invalid tenant member credentials"
                    : "Ambiguous tenant member login");
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

    @PostMapping("/admin")
    public LoginResponse adminLogin(@RequestBody LoginRequest req, HttpServletRequest request) {
        if ("admin".equals(req.name()) && "admin123".equals(req.code())) {
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
