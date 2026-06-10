export async function render(container, params) {
    var principal = window.CURRENT_PRINCIPAL || {};
    var tenantId = principal.tenantId || localStorage.getItem('tenant_id') || '';
    var tenantName = principal.tenantName || localStorage.getItem('tenant_name') || '';

    container.innerHTML = '' +
        '<div class="page">' +
        '<h1>Settings</h1>' +
        '<p class="subtitle">Tenant profile configuration</p>' +
        '<div id="settings-content"></div>' +
        '</div>';

    var contentEl = container.querySelector('#settings-content');
    contentEl.innerHTML = '<div class="placeholder-card"><p>Loading...</p></div>';

    try {
        var ops = await window.api.get('/api/ops/tenant');
        renderSettings(contentEl, ops);
    } catch (err) {
        contentEl.innerHTML = '<div class="placeholder-card"><p>Failed to load: ' + err.message + '</p></div>';
    }

    function renderSettings(el, ops) {
        var runtime = ops.runtime || {};
        var kb = ops.knowledgeBase || {};
        var bots = ops.bots || [];
        var pr = ops.purchaseRequests || {};

        el.innerHTML = '' +
            '<div class="settings-grid">' +
                '<div class="settings-card">' +
                    '<h3>Tenant Info</h3>' +
                    '<div class="settings-row"><span class="settings-label">Tenant ID</span><span class="settings-value">' + tenantId + '</span></div>' +
                    '<div class="settings-row"><span class="settings-label">Tenant Name</span><span class="settings-value">' + tenantName + '</span></div>' +
                    '<div class="settings-row"><span class="settings-label">Role</span><span class="settings-value">' + (principal.role || '-') + '</span></div>' +
                    '<div class="settings-row"><span class="settings-label">User</span><span class="settings-value">' + (principal.displayName || principal.email || '-') + '</span></div>' +
                '</div>' +
                '<div class="settings-card">' +
                    '<h3>Runtime</h3>' +
                    '<div class="settings-row"><span class="settings-label">Status</span><span class="settings-value">' + (runtime.status || 'UNKNOWN') + '</span></div>' +
                    '<div class="settings-row"><span class="settings-label">Last Activity</span><span class="settings-value">' + (runtime.lastActivityAt ? new Date(runtime.lastActivityAt).toLocaleString() : '-') + '</span></div>' +
                    '<div style="margin-top: 12px;"><button class="btn btn-secondary" id="btn-evict-runtime">Evict Runtime Cache</button></div>' +
                '</div>' +
                '<div class="settings-card">' +
                    '<h3>Knowledge Base</h3>' +
                    '<div class="settings-row"><span class="settings-label">Status</span><span class="settings-value">' + (kb.status || 'UNKNOWN') + '</span></div>' +
                    '<div class="settings-row"><span class="settings-label">Last Rebuild</span><span class="settings-value">' + (kb.lastRebuildAt ? new Date(kb.lastRebuildAt).toLocaleString() : '-') + '</span></div>' +
                    '<div style="margin-top: 12px;"><button class="btn btn-secondary" id="btn-rebuild-from-settings">Rebuild KB</button></div>' +
                '</div>' +
                '<div class="settings-card">' +
                    '<h3>Summary</h3>' +
                    '<div class="settings-row"><span class="settings-label">Chatbots</span><span class="settings-value">' + bots.length + '</span></div>' +
                    '<div class="settings-row"><span class="settings-label">Purchase Requests</span><span class="settings-value">' + (pr.totalRequests || 0) + '</span></div>' +
                    '<div class="settings-row"><span class="settings-label">New PRs</span><span class="settings-value">' + (pr.newCount || 0) + '</span></div>' +
                    '<div class="settings-row"><span class="settings-label">Completed PRs</span><span class="settings-value">' + (pr.completedCount || 0) + '</span></div>' +
                '</div>' +
            '</div>';

        el.querySelector('#btn-evict-runtime').addEventListener('click', function() {
            window.api.post('/api/ops/runtime/evict')
                .then(function(res) {
                    window.showToast(res.message || 'Runtime evicted', 'success');
                })
                .catch(function(err) { window.showToast('Failed: ' + err.message, 'error'); });
        });

        el.querySelector('#btn-rebuild-from-settings').addEventListener('click', function() {
            window.showToast('KB rebuild started...', 'info');
            window.api.post('/api/kb/rebuild')
                .then(function(res) {
                    window.showToast(res.message || 'Rebuild completed', 'success');
                })
                .catch(function(err) { window.showToast('Failed: ' + err.message, 'error'); });
        });
    }
}
