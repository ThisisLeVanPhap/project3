export async function render(container, params) {
    container.innerHTML = '' +
        '<div class="page">' +
        '<h1>Knowledge Base</h1>' +
        '<p class="subtitle">Data sources and rebuild history</p>' +
        '<div class="toolbar">' +
        '<input type="text" class="form-input" id="kb-url-input" placeholder="https://example.com/help" style="flex: 1; max-width: 400px;">' +
        '<button class="btn btn-primary" id="btn-add-source">+ Add Source</button>' +
        '<button class="btn btn-secondary" id="btn-rebuild-kb" style="margin-left: auto;">Rebuild KB</button>' +
        '</div>' +
        '<div id="kb-content"></div>' +
        '</div>';

    var contentEl = container.querySelector('#kb-content');

    loadSources();

    container.querySelector('#btn-add-source').addEventListener('click', function() {
        var url = container.querySelector('#kb-url-input').value.trim();
        if (!url) { window.showToast('Enter a URL', 'warning'); return; }
        window.api.post('/api/kb/source-urls', { url: url })
            .then(function() {
                window.showToast('Source added', 'success');
                container.querySelector('#kb-url-input').value = '';
                loadSources();
            })
            .catch(function(err) { window.showToast('Failed: ' + err.message, 'error'); });
    });

    container.querySelector('#btn-rebuild-kb').addEventListener('click', function() {
        window.showToast('KB rebuild started...', 'info');
        window.api.post('/api/kb/rebuild')
            .then(function(res) {
                window.showToast(res.message || 'Rebuild completed', 'success');
                loadOpsStatus();
            })
            .catch(function(err) { window.showToast('Failed: ' + err.message, 'error'); });
    });

    async function loadSources() {
        contentEl.innerHTML = '<div class="skeleton-container">' +
            '<div class="skeleton skeleton-title"></div>' +
            '<div class="skeleton skeleton-card"></div>' +
            '<div class="skeleton skeleton-card"></div>' +
            '</div>';
        try {
            var res = await window.api.get('/api/kb/source-urls');
            var urls = res.urls || [];
            renderSources(contentEl, urls);
            loadOpsStatus();
        } catch (err) {
            contentEl.innerHTML = '<div class="placeholder-card"><p>Failed to load: ' + err.message + '</p></div>';
        }
    }

    function renderSources(el, urls) {
        if (!urls.length) {
            el.innerHTML = '<div class="empty-state">' +
                '<div class="icon">📚</div>' +
                '<div class="title">No knowledge base sources</div>' +
                '<div class="description">Add source URLs to build your chatbot knowledge base.</div>' +
                '</div>';
            return;
        }

        window.createTable(el, {
            columns: [
                { key: 'url', label: 'Source URL', sortable: true, render: function(row) {
                    var u = row.url || '';
                    return '<a href="' + u + '" target="_blank" style="color: var(--primary);">' + u + '</a>';
                }},
                { key: 'actions', label: 'Actions', render: function(row) {
                    var u = row.url || '';
                    return '<button class="btn btn-secondary btn-sm" data-url="' + u + '">Remove</button>';
                }}
            ],
            data: urls.map(function(u) { return { url: u, _raw: u }; }),
            emptyMessage: 'No sources'
        });

        el.querySelectorAll('[data-url]').forEach(function(btn) {
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                var url = btn.getAttribute('data-url');
                window.showConfirm('Remove Source', 'Remove "' + url + '"?')
                    .then(function(confirmed) {
                        if (!confirmed) return;
                        window.api.del('/api/kb/source-urls', { url: url })
                            .then(function() {
                                window.showToast('Source removed', 'success');
                                loadSources();
                            })
                            .catch(function(err) { window.showToast('Failed: ' + err.message, 'error'); });
                    });
            });
        });
    }

    async function loadOpsStatus() {
        try {
            var ops = await window.api.get('/api/ops/tenant');
            var kb = ops.knowledgeBase || {};
            var historyHtml = '';
            if (kb.rebuildHistory && kb.rebuildHistory.length) {
                historyHtml = '<div class="kb-history"><h3>Recent Rebuilds</h3>';
                kb.rebuildHistory.slice(0, 5).forEach(function(h) {
                    var cls = h.status === 'SUCCESS' ? 'badge-status-active' : h.status === 'FAILED' ? 'badge-status-inactive' : 'badge-provider';
                    historyHtml += '<div class="kb-history-item">' +
                        '<span class="badge ' + cls + '">' + (h.status || 'UNKNOWN') + '</span>' +
                        '<span>' + (h.startedAt ? new Date(h.startedAt).toLocaleString() : '-') + '</span>' +
                        '<span class="muted">' + (h.message || '') + '</span>' +
                        '</div>';
                });
                historyHtml += '</div>';
            }
            var existing = contentEl.querySelector('.kb-history');
            if (existing) existing.remove();
            contentEl.insertAdjacentHTML('beforeend', historyHtml);
        } catch (err) {
            // silent
        }
    }
}
