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
            await loadActiveProducts(kb);
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

    async function loadActiveProducts(kb) {
        if (kb.status !== 'READY') {
            return;
        }
        var emptyState = contentEl.querySelector('.empty-state');
        if (!emptyState) {
            return;
        }
        try {
            var active = await window.api.get('/api/kb/active-products?limit=50');
            if (!active || !active.total) {
                return;
            }
            emptyState.outerHTML = renderActiveDatasetKb(kb, active);
        } catch (err) {
            // The manual source list can still be managed even if active products are unavailable.
        }
    }

    function renderActiveDatasetKb(kb, active) {
        var sourceUrl = kb.sourceUrl || '';
        var source = kb.source || '-';
        var datasetId = kb.datasetId || '-';
        var sourceType = kb.sourceType || 'ACTIVE_VERSION';
        var kbDir = active.kbDir || kb.kbDir || '';
        var count = active.total != null ? active.total : (kb.artifactCount != null ? kb.artifactCount : '-');
        var products = Array.isArray(active.products) ? active.products : [];
        var rows = products.map(function(product) {
            var url = product.url || '';
            return '<tr>' +
                '<td>' + escapeHtml(product.name || '-') + '</td>' +
                '<td>' + escapeHtml(product.sku || '-') + '</td>' +
                '<td>' + escapeHtml(product.category || '-') + '</td>' +
                '<td>' + (url ? '<a href="' + escapeHtml(url) + '" target="_blank" style="color: var(--primary);">' + escapeHtml(url) + '</a>' : '-') + '</td>' +
                '</tr>';
        }).join('');
        return '<div class="card2" style="padding: 16px; margin-top: 16px;">' +
            '<h3 style="margin-top:0;">Active dataset KB</h3>' +
            '<div class="settings-row"><span class="settings-label">Status</span><span class="settings-value">' + escapeHtml(kb.status || '-') + '</span></div>' +
            '<div class="settings-row"><span class="settings-label">Source type</span><span class="settings-value">' + escapeHtml(sourceType) + '</span></div>' +
            '<div class="settings-row"><span class="settings-label">Dataset</span><span class="settings-value">' + escapeHtml(datasetId) + '</span></div>' +
            '<div class="settings-row"><span class="settings-label">Source</span><span class="settings-value">' + escapeHtml(source) + '</span></div>' +
            '<div class="settings-row"><span class="settings-label">Source URL</span><span class="settings-value">' + (sourceUrl ? '<a href="' + escapeHtml(sourceUrl) + '" target="_blank" style="color: var(--primary);">' + escapeHtml(sourceUrl) + '</a>' : '-') + '</span></div>' +
            '<div class="settings-row"><span class="settings-label">Artifacts</span><span class="settings-value">' + escapeHtml(String(count)) + '</span></div>' +
            '<div class="settings-row"><span class="settings-label">KB directory</span><span class="settings-value">' + escapeHtml(kbDir) + '</span></div>' +
            '<p class="muted">This tenant is using a built product dataset artifact. The curated URL list above is only for manual URL/sitemap rebuilds.</p>' +
            '<div class="table-wrap"><table class="data-table"><thead><tr><th>Product</th><th>SKU</th><th>Category</th><th>URL</th></tr></thead><tbody>' + rows + '</tbody></table></div>' +
            '<p class="muted" style="margin-bottom:0;">Showing ' + products.length + ' of ' + escapeHtml(String(count)) + ' active KB products.</p>' +
            '</div>';
    }

    function escapeHtml(value) {
        return String(value == null ? '' : value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }
}
