export async function render(container, params) {
    container.innerHTML = '' +
        '<div class="page">' +
        '<h1>Knowledge Base</h1>' +
        '<p class="subtitle">Product URLs, product sitemap source, and rebuild history</p>' +
        '<div class="toolbar" style="gap: 8px; flex-wrap: wrap;">' +
        '<input type="text" class="form-input" id="kb-url-input" placeholder="https://example.com/product/123" style="flex: 1; min-width: 260px;">' +
        '<button class="btn btn-primary" id="btn-add-source">+ Add Product URL</button>' +
        '<input type="text" class="form-input" id="kb-sitemap-input" placeholder="https://moho.com.vn/sitemap_products_1.xml" style="flex: 1; min-width: 260px;">' +
        '<button class="btn btn-secondary" id="btn-set-sitemap">Set Product Sitemap</button>' +
        '<button class="btn btn-secondary" id="btn-rebuild-kb" style="margin-left: auto;">Rebuild KB</button>' +
        '</div>' +
        '<div id="kb-content"></div>' +
        '</div>';

    var contentEl = container.querySelector('#kb-content');

    loadSources();

    container.querySelector('#btn-add-source').addEventListener('click', function() {
        var url = container.querySelector('#kb-url-input').value.trim();
        if (!url) { window.showToast('Enter a product URL', 'warning'); return; }
        window.api.post('/api/kb/source-urls', { url: url })
            .then(function() {
                window.showToast('Product URL added', 'success');
                container.querySelector('#kb-url-input').value = '';
                loadSources();
            })
            .catch(function(err) { window.showToast('Failed: ' + err.message, 'error'); });
    });

    container.querySelector('#btn-set-sitemap').addEventListener('click', function() {
        var sitemapUrl = container.querySelector('#kb-sitemap-input').value.trim();
        if (!sitemapUrl) { window.showToast('Enter a sitemap/root URL', 'warning'); return; }
        window.api.post('/api/kb/source-urls/sitemap', { sitemapUrl: sitemapUrl })
            .then(function() {
                window.showToast('Sitemap source updated', 'success');
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
            var sourceRes = await window.api.get('/api/kb/source-urls');
            var configRes = await window.api.get('/api/kb/source-urls/config');
            var urls = sourceRes.urls || [];
            renderSources(contentEl, urls, configRes.source || {});
            var sitemapInput = container.querySelector('#kb-sitemap-input');
            if (sitemapInput && (configRes.source || {}).sitemapUrl) {
                sitemapInput.value = configRes.source.sitemapUrl;
            }
            loadOpsStatus();
        } catch (err) {
            contentEl.innerHTML = '<div class="placeholder-card"><p>Failed to load: ' + err.message + '</p></div>';
        }
    }

    function renderSources(el, urls, source) {
        var mode = source.mode || 'PRODUCT_URL_LIST';
        var sitemapUrl = source.sitemapUrl || source.sourceUrl || '';
        var provider = source.provider || '-';
        var summary = '<div class="card2" style="margin-bottom: 16px; padding: 16px;">' +
            '<div><b>Current source mode:</b> ' + mode + '</div>' +
            '<div class="muted">Provider: ' + provider + '</div>' +
            '<div class="muted">Sitemap/root URL: ' + (sitemapUrl || '-') + '</div>' +
            '</div>';

        if (!urls.length) {
            el.innerHTML = summary + '<div class="empty-state">' +
                '<div class="icon">📚</div>' +
                '<div class="title">No product URLs curated yet</div>' +
                '<div class="description">Add product URLs directly, or set a sitemap/root URL before rebuilding.</div>' +
                '</div>';
            return;
        }

        el.innerHTML = summary + '<div id="kb-source-table"></div>';
        var tableEl = el.querySelector('#kb-source-table');
        window.createTable(tableEl, {
            columns: [
                { key: 'url', label: 'Product URL', sortable: true, render: function(row) {
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

        tableEl.querySelectorAll('[data-url]').forEach(function(btn) {
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                var url = btn.getAttribute('data-url');
                window.showConfirm('Remove Product URL', 'Remove "' + url + '"?')
                    .then(function(confirmed) {
                        if (!confirmed) return;
                        window.api.del('/api/kb/source-urls', { url: url })
                            .then(function() {
                                window.showToast('Product URL removed', 'success');
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
