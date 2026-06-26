(function() {
    'use strict';

    var routes = {
        '/dashboard': { module: './pages/dashboard.js', title: 'Dashboard', adminOnly: false },
        '/leads': { module: './pages/leads.js', title: 'Leads', adminOnly: false },
        '/purchase-requests': { module: './pages/purchase-requests.js', title: 'Purchase Requests', adminOnly: false },
        '/members': { module: './pages/members.js', title: 'Members', adminOnly: true },
        '/chatbots': { module: './pages/chatbots.js', title: 'Chatbots', adminOnly: true },
        '/kb': { module: './pages/kb.js', title: 'Knowledge Base', adminOnly: true },
        '/bindings': { module: './pages/bindings.js', title: 'Bindings', adminOnly: true },
        '/settings': { module: './pages/settings.js', title: 'Settings', adminOnly: true }
    };

    function parseHash() {
        var hash = window.location.hash || '#/dashboard';
        hash = hash.replace(/^#/, '');
        var parts = hash.split('/').filter(Boolean);
        return {
            path: '/' + (parts[0] || 'dashboard'),
            params: parts.slice(1)
        };
    }

    function updateActiveLink(path) {
        var links = document.querySelectorAll('.sidebar-nav a');
        links.forEach(function(link) {
            var href = link.getAttribute('href');
            if (href === '#' + path || (path === '/leads' && href && href.indexOf('#/leads') === 0)) {
                link.classList.add('active');
            } else {
                link.classList.remove('active');
            }
        });
    }

    function navigate() {
        var parsed = parseHash();
        var route = routes[parsed.path];

        if (!route) {
            window.location.hash = '#/dashboard';
            return;
        }

        var principal = window.CURRENT_PRINCIPAL;
        if (route.adminOnly && principal && principal.role !== 'TENANT_ADMIN') {
            if (window.showToast) window.showToast('Not authorized', 'error');
            window.location.hash = '#/dashboard';
            return;
        }

        var pageTitle = document.getElementById('pageTitle');
        if (pageTitle) pageTitle.textContent = route.title;
        document.title = route.title + ' - Tenant Workspace';

        updateActiveLink(parsed.path);

        var app = document.getElementById('app');
        if (!app) return;

        app.innerHTML = '<div class="page"><h1>Loading...</h1></div>';

        var cacheBuster = '?v=' + (new Date()).getTime();
        import(route.module + cacheBuster)
            .then(function(module) {
                if (module && module.render) {
                    return module.render(app, parsed.params);
                }
            })
            .catch(function(err) {
                app.innerHTML = '<div class="page"><h1>Error</h1><p class="subtitle">' + err.message + '</p></div>';
                console.error('Router error:', err);
            });
    }

    window.addEventListener('hashchange', navigate);

    window.startRouter = function() {
        if (!window.location.hash) {
            window.location.hash = '#/dashboard';
        } else {
            navigate();
        }
    };
})();
