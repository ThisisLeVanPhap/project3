(function() {
    'use strict';

    // Global error boundary
    window.addEventListener('error', function(e) {
        console.error('Global error:', e.error);
        var msg = e.error ? e.error.message : 'An unexpected error occurred';
        if (window.showToast) {
            window.showToast('Error: ' + msg, 'error');
        }
    });

    window.addEventListener('unhandledrejection', function(e) {
        console.error('Unhandled promise rejection:', e.reason);
        var msg = e.reason ? (e.reason.message || String(e.reason)) : 'An unexpected error occurred';
        if (window.showToast) {
            window.showToast('Error: ' + msg, 'error');
        }
    });

    // ===== Toast helper =====
    function showToast(message, type) {
        type = type || 'info';
        var container = document.getElementById('toast-container');
        if (!container) return;
        var el = document.createElement('div');
        el.className = 'toast ' + type;
        el.textContent = message;
        container.appendChild(el);
        setTimeout(function() {
            el.style.opacity = '0';
            el.style.transition = 'opacity 0.3s';
            setTimeout(function() { container.removeChild(el); }, 300);
        }, 3000);
    }
    window.showToast = showToast;

    // ===== Auth check =====
    fetch('/api/me', { credentials: 'same-origin' })
        .then(function(res) {
            if (res.status === 401) {
                window.location.href = '/login';
                throw new Error('Unauthorized');
            }
            if (!res.ok) throw new Error('Auth check failed');
            return res.json();
        })
        .then(function(principal) {
            if (principal.role === 'PLATFORM_ADMIN') {
                window.location.href = '/admin';
                return;
            }
            window.CURRENT_PRINCIPAL = principal;
            renderShell(principal);
            setupLogout();
            // Load additional scripts then start router
            loadScripts([
                '/tenant/lib/toast.js',
                '/tenant/api.js',
                '/tenant/lib/drawer.js',
                '/tenant/lib/modal.js',
                '/tenant/lib/table.js',
                '/tenant/router.js'
            ]).then(function() {
                if (window.startRouter) window.startRouter();

                // Session expiry check - poll every 5 minutes
                var sessionCheckInterval = setInterval(function() {
                    fetch('/api/me', { credentials: 'same-origin' })
                        .then(function(res) {
                            if (res.status === 401) {
                                if (window.showToast) window.showToast('Session expired. Redirecting...', 'warning');
                                setTimeout(function() {
                                    window.location.href = '/login';
                                }, 2000);
                            }
                        })
                        .catch(function() {});
                }, 300000); // 5 minutes

                // Store interval ID for cleanup
                window.appIntervals = window.appIntervals || [];
                window.appIntervals.push(sessionCheckInterval);
            });
        })
        .catch(function(err) {
            if (err.message !== 'Unauthorized') {
                showToast('Failed to load session: ' + err.message, 'error');
            }
        });

    // ===== Render sidebar =====
    function renderShell(principal) {
        var tenantLabel = document.getElementById('tenantLabel');
        var identityLabel = document.getElementById('identityLabel');
        var roleLabel = document.getElementById('roleLabel');
        if (tenantLabel) tenantLabel.textContent = principal.tenantName || principal.tenantId || '—';
        if (identityLabel) identityLabel.textContent = principal.displayName || principal.email || '-';
        if (roleLabel) roleLabel.textContent = (principal.role || '-').replace('_', ' ');

        if (principal.tenantId) localStorage.setItem('tenant_id', principal.tenantId);
        if (principal.tenantName) localStorage.setItem('tenant_name', principal.tenantName);

        var nav = document.getElementById('sidebarNav');
        if (!nav) return;

        var links = [
            { href: '#/dashboard', label: 'Dashboard', icon: '📊', adminOnly: false },
            { href: '#/leads', label: 'Leads', icon: '🎯', adminOnly: false },
            { href: '#/purchase-requests', label: 'Purchase Requests', icon: '📦', adminOnly: false },
            { href: '#/members', label: 'Members', icon: '👥', adminOnly: true },
            { href: '#/chatbots', label: 'Chatbots', icon: '🤖', adminOnly: true },
            { href: '#/kb', label: 'Knowledge Base', icon: '📚', adminOnly: true },
            { href: '#/bindings', label: 'Bindings', icon: '🔗', adminOnly: true },
            { href: '#/settings', label: 'Settings', icon: '⚙️', adminOnly: true }
        ];

        var isAdmin = principal.role === 'TENANT_ADMIN';
        nav.innerHTML = '';
        links.forEach(function(link) {
            if (link.adminOnly && !isAdmin) return;
            var a = document.createElement('a');
            a.href = link.href;
            a.innerHTML = '<span class="icon">' + link.icon + '</span><span class="label">' + link.label + '</span>';
            nav.appendChild(a);
        });

        var hash = window.location.hash || '#/dashboard';
        var activeLink = nav.querySelector('a[href="' + hash + '"]');
        if (activeLink) activeLink.classList.add('active');

        var app = document.getElementById('app');
        if (app) {
            app.innerHTML = '<div class="page"><h1>Loading...</h1></div>';
        }
    }

    // ===== Dynamic script loader =====
    function loadScripts(srcs) {
        var promises = srcs.map(function(src) {
            return new Promise(function(resolve, reject) {
                var s = document.createElement('script');
                s.src = src;
                s.onload = resolve;
                s.onerror = function() { reject(new Error('Failed to load ' + src)); };
                document.head.appendChild(s);
            });
        });
        return Promise.all(promises);
    }

    // ===== Logout =====
    function setupLogout() {
        var btn = document.getElementById('btn-logout');
        if (!btn) return;
        btn.addEventListener('click', function() {
            fetch('/api/login/logout', { method: 'POST', credentials: 'same-origin' })
                .catch(function() {})
                .then(function() {
                    localStorage.removeItem('tenant_id');
                    localStorage.removeItem('tenant_name');
                    // Clear all running intervals
                    if (window.appIntervals) {
                        window.appIntervals.forEach(function(id) { clearInterval(id); });
                    }
                    window.location.href = '/login';
                });
        });
    }
})();
