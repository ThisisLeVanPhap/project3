export async function render(container, params) {
    var principal = window.CURRENT_PRINCIPAL || {};
    var displayName = principal.displayName || principal.email || 'User';
    var role = (principal.role || '-').replace('_', ' ');

    container.innerHTML = '<div class="page">' +
        '<h1>Dashboard</h1>' +
        '<p class="subtitle">Welcome, <strong>' + displayName + '</strong> (' + role + ')</p>' +
        '<div class="stat-grid" id="stats">' +
        '<div class="stat-card"><div class="label">Loading...</div><div class="value">—</div></div>' +
        '</div>' +
        '<div id="analytics-section"></div>' +
        '<div class="activity-section" id="activity-section">' +
        '<h2>Recent Activity</h2>' +
        '<div id="activity-feed"><div class="skeleton skeleton-text"></div><div class="skeleton skeleton-text"></div><div class="skeleton skeleton-text"></div></div>' +
        '</div>' +
        '</div>';

    try {
        var res = await window.api.get('/api/ops/tenant');
        var pr = res.purchaseRequests || {};
        var kb = res.knowledgeBase || {};
        var runtime = res.runtime || {};
        var bots = Array.isArray(res.bots) ? res.bots : [];

        var statsEl = container.querySelector('#stats');
        if (statsEl) {
            statsEl.innerHTML = '' +
                '<div class="stat-card"><div class="label">Purchase Requests</div><div class="value">' + (pr.totalRequests != null ? pr.totalRequests : 0) + '</div></div>' +
                '<div class="stat-card"><div class="label">New PRs</div><div class="value">' + (pr.newCount != null ? pr.newCount : 0) + '</div></div>' +
                '<div class="stat-card"><div class="label">Chatbots</div><div class="value">' + bots.length + '</div></div>' +
                '<div class="stat-card"><div class="label">KB Status</div><div class="value">' + (kb.status || 'N/A') + '</div></div>';
        }

        var analyticsEl = container.querySelector('#analytics-section');
        if (analyticsEl) {
            var html = '<h2>Detailed Analytics</h2>' +
                '<div class="settings-grid">';

            // Purchase Request Breakdown
            html += '<div class="settings-card">' +
                '<h3>Purchase Request Pipeline</h3>' +
                '<div class="settings-row"><span class="settings-label">Total</span><span class="settings-value">' + (pr.totalRequests || 0) + '</span></div>' +
                '<div class="settings-row"><span class="settings-label">New</span><span class="settings-value">' + (pr.newCount || 0) + '</span></div>' +
                '<div class="settings-row"><span class="settings-label">Contacted</span><span class="settings-value">' + (pr.contactedCount || 0) + '</span></div>' +
                '<div class="settings-row"><span class="settings-label">Completed</span><span class="settings-value">' + (pr.completedCount || 0) + '</span></div>' +
                '<div class="settings-row"><span class="settings-label">Assigned</span><span class="settings-value">' + (pr.assignedCount || 0) + '</span></div>' +
                '</div>';

            // Knowledge Base Info
            html += '<div class="settings-card">' +
                '<h3>Knowledge Base</h3>' +
                '<div class="settings-row"><span class="settings-label">Status</span><span class="settings-value">' + (kb.status || 'N/A') + '</span></div>' +
                '<div class="settings-row"><span class="settings-label">Documents</span><span class="settings-value">' + (kb.documentCount != null ? kb.documentCount : 'N/A') + '</span></div>' +
                '<div class="settings-row"><span class="settings-label">Last Rebuild</span><span class="settings-value">' + (kb.lastRebuildAt ? new Date(kb.lastRebuildAt).toLocaleString() : 'Never') + '</span></div>' +
                '</div>';

            // Runtime Status
            html += '<div class="settings-card">' +
                '<h3>AI Runtime</h3>' +
                '<div class="settings-row"><span class="settings-label">Active</span><span class="settings-value">' + (runtime.active ? 'Yes' : 'No') + '</span></div>' +
                '<div class="settings-row"><span class="settings-label">Model</span><span class="settings-value">' + (runtime.modelId || 'N/A') + '</span></div>' +
                '<div class="settings-row"><span class="settings-label">Session Age</span><span class="settings-value">' + (runtime.sessionAgeSeconds != null ? Math.floor(runtime.sessionAgeSeconds / 60) + 'm' : 'N/A') + '</span></div>' +
                '</div>';

            // Chatbots List
            html += '<div class="settings-card">' +
                '<h3>Chatbots (' + bots.length + ')</h3>';
            if (bots.length === 0) {
                html += '<p style="color:var(--muted);font-size:14px;">No chatbots configured.</p>';
            } else {
                bots.forEach(function(bot) {
                    html += '<div class="settings-row"><span class="settings-label">' + (bot.name || bot.id) + '</span><span class="settings-value">' + (bot.baseModel || 'unknown') + '</span></div>';
                });
            }
            html += '</div>';

            html += '</div>';
            analyticsEl.innerHTML = html;
        }
    } catch (err) {
        console.error('Dashboard stats error:', err);
        if (window.showToast) window.showToast('Failed to load stats: ' + err.message, 'error');
    }

    try {
        var activities = await window.api.get('/tenant/api/activity?limit=10');
        var feedEl = container.querySelector('#activity-feed');
        if (feedEl) {
            if (!activities || activities.length === 0) {
                feedEl.innerHTML = '<div class="empty-state"><div class="icon">📭</div><div class="title">No recent activity</div><div class="description">New leads and actions will appear here.</div></div>';
            } else {
                feedEl.innerHTML = activities.map(function(act) {
                    var time = act.timestamp ? new Date(act.timestamp).toLocaleString() : 'Recently';
                    return '<div class="activity-item">' +
                        '<div class="activity-time">' + time + '</div>' +
                        '<div class="activity-label">' + (act.label || '') + '</div>' +
                        (act.details ? '<div class="activity-details">' + act.details + '</div>' : '') +
                        '</div>';
                }).join('');
            }
        }

        var pollInterval = setInterval(async function() {
            if (window.location.hash !== '#/dashboard' && window.location.hash !== '#/dashboard/') {
                clearInterval(pollInterval);
                return;
            }
            try {
                var freshActivities = await window.api.get('/tenant/api/activity?limit=10');
                var freshFeedEl = container.querySelector('#activity-feed');
                if (freshFeedEl && freshActivities && freshActivities.length > 0) {
                    freshFeedEl.innerHTML = freshActivities.map(function(act) {
                        var t = act.timestamp ? new Date(act.timestamp).toLocaleString() : 'Recently';
                        return '<div class="activity-item">' +
                            '<div class="activity-time">' + t + '</div>' +
                            '<div class="activity-label">' + (act.label || '') + '</div>' +
                            (act.details ? '<div class="activity-details">' + act.details + '</div>' : '') +
                            '</div>';
                    }).join('');
                }
            } catch (e) {
                // Silent fail for polling
            }
        }, 30000);

        window.appIntervals = window.appIntervals || [];
        window.appIntervals.push(pollInterval);

        var cleanupHandler = function() {
            if (window.location.hash !== '#/dashboard' && window.location.hash !== '#/dashboard/') {
                clearInterval(pollInterval);
                window.removeEventListener('hashchange', cleanupHandler);
            }
        };
        window.addEventListener('hashchange', cleanupHandler);
    } catch (err) {
        console.error('Dashboard activity feed error:', err);
        var feedEl = container.querySelector('#activity-feed');
        if (feedEl) {
            var errMsg = err && err.message ? err.message : 'Unknown error';
            feedEl.innerHTML = '<div class="empty-state"><div class="icon">⚠️</div><div class="title">Activity feed unavailable</div><div class="description">' + errMsg + '</div></div>';
        }
    }
}