export async function render(container, params) {
    var tenantId = localStorage.getItem('tenant_id') || '';

    container.innerHTML = '' +
        '<div class="page">' +
        '<h1>Leads</h1>' +
        '<p class="subtitle">Customer leads from chatbot conversations</p>' +
        '<div class="toolbar"><button class="btn btn-secondary" id="btn-export-csv">📥 Export CSV</button></div>' +
        '<div class="filter-bar" style="margin-bottom: 16px;">' +
        '<select id="filter-status">' +
        '<option value="">All Statuses</option>' +
        '<option value="NEW">NEW</option>' +
        '<option value="CONTACTED">CONTACTED</option>' +
        '<option value="CONVERTED">CONVERTED</option>' +
        '<option value="FALSE_SIGNAL">FALSE SIGNAL</option>' +
        '<option value="CLOSED">CLOSED</option>' +
        '</select>' +
        '<select id="filter-stage">' +
        '<option value="">All Stages</option>' +
        '<option value="DISCOVER">DISCOVER</option>' +
        '<option value="SUGGEST">SUGGEST</option>' +
        '<option value="CONFIRM">CONFIRM</option>' +
        '<option value="HANDOFF">HANDOFF</option>' +
        '<option value="FULFILLED">FULFILLED</option>' +
        '</select>' +
        '<input type="date" id="filter-from" placeholder="From">' +
        '<input type="date" id="filter-to" placeholder="To">' +
        '<button class="btn btn-secondary" id="btn-clear-filters">Clear</button>' +
        '</div>' +
        '<div class="bulk-bar" id="bulk-bar" style="display: none; margin-bottom: 16px; padding: 12px; background: #f1f5f9; border-radius: 6px;">' +
        '<span id="selected-count">0</span> selected ' +
        '<button class="btn btn-secondary" id="bulk-contacted">Mark Contacted</button>' +
        '<button class="btn btn-secondary" id="bulk-closed">Mark Closed</button>' +
        '</div>' +
        '<div id="leads-content"></div>' +
        '</div>';

    var contentEl = container.querySelector('#leads-content');
    var allData = null;
    var selectedIds = new Set();
    var filteredData = null;

    // Show skeleton loading
    contentEl.innerHTML = '<div class="skeleton-container">' +
        '<div class="skeleton skeleton-title"></div>' +
        '<div class="skeleton skeleton-card"></div>' +
        '<div class="skeleton skeleton-card"></div>' +
        '</div>';

    // Setup export button
    var exportBtn = container.querySelector('#btn-export-csv');
    if (exportBtn) {
        exportBtn.addEventListener('click', function() {
            if (!allData || !allData.length) {
                if (window.showToast) window.showToast('No data to export', 'warning');
                return;
            }
            var headers = ['id','createdAt','channel','customerHandle','status','stage'];
            var rows = allData.map(function(row) {
                return headers.map(function(h) {
                    var v = row[h] || '';
                    return '"' + String(v).replace(/"/g, '""') + '"';
                }).join(',');
            });
            var csv = [headers.join(',')].concat(rows).join('\n');
            var blob = new Blob([csv], { type: 'text/csv' });
            var url = URL.createObjectURL(blob);
            var a = document.createElement('a');
            a.href = url;
            a.download = 'leads-' + new Date().toISOString().slice(0,10) + '.csv';
            a.click();
            URL.revokeObjectURL(url);
            if (window.showToast) window.showToast('Exported ' + allData.length + ' leads', 'success');
        });
    }

    try {
        var leads = await window.api.get('/tenant/api/leads?tid=' + encodeURIComponent(tenantId));
        allData = leads;
        renderLeadsTable(contentEl, leads);
    } catch (err) {
        contentEl.innerHTML = '<div class="placeholder-card"><p>Failed to load leads: ' + err.message + '</p></div>';
    }

    function filterData(data) {
        var statusFilter = document.getElementById('filter-status').value;
        var stageFilter = document.getElementById('filter-stage').value;
        var fromDate = document.getElementById('filter-from').value;
        var toDate = document.getElementById('filter-to').value;

        return data.filter(function(row) {
            if (statusFilter && row.status !== statusFilter) return false;
            if (stageFilter && row.stage !== stageFilter) return false;
            if (fromDate && row.createdAt) {
                var rowDate = new Date(row.createdAt).toISOString().split('T')[0];
                if (rowDate < fromDate) return false;
            }
            if (toDate && row.createdAt) {
                var rowDate = new Date(row.createdAt).toISOString().split('T')[0];
                if (rowDate > toDate) return false;
            }

            return true;
        });
    }

    function updateBulkBar() {
        var bulkBar = document.getElementById('bulk-bar');
        var countEl = document.getElementById('selected-count');
        if (bulkBar && countEl) {
            countEl.textContent = selectedIds.size;
            bulkBar.style.display = selectedIds.size > 0 ? 'block' : 'none';
        }
    }

    async function bulkUpdateStatus(status) {
        if (selectedIds.size === 0) return;

        if (window.showToast) window.showToast('Updating ' + selectedIds.size + ' leads...', 'info');

        var promises = Array.from(selectedIds).map(function(id) {
            return window.api.post('/tenant/api/leads/' + id + '/status?status=' + status + '&tid=' + encodeURIComponent(tenantId));
        });

        try {
            await Promise.all(promises);
            if (window.showToast) window.showToast('Updated ' + selectedIds.size + ' leads to ' + status, 'success');
            selectedIds.clear();
            render(container, params);
        } catch (err) {
            if (window.showToast) window.showToast('Bulk update failed: ' + err.message, 'error');
        }
    }

    function renderLeadsTable(el, data) {
        if (!data || !data.length) {
            el.innerHTML = '<div class="empty-state">' +
                '<div class="icon">🎯</div>' +
                '<div class="title">No leads yet</div>' +
                '<div class="description">Leads will appear here when the chatbot hands off conversations.</div>' +
                '</div>';
            return;
        }

        filteredData = filterData(data);

        window.createTable(el, {
            columns: [
                { key: 'select', label: '<input type="checkbox" id="select-all">', render: function(row) {
                    return '<input type="checkbox" class="row-select" data-id="' + row.id + '" ' +
                           (selectedIds.has(row.id) ? 'checked' : '') + '>';
                }},
                { key: 'id', label: 'ID', sortable: true },
                { key: 'createdAt', label: 'Created', sortable: true, render: function(row) {
                    return row.createdAt ? new Date(row.createdAt).toLocaleString() : '-';
                }},
                { key: 'status', label: 'Status', sortable: true, render: function(row) {
                    var s = row.status || 'NEW';
                    var cls = statusBadgeClass(s);
                    return '<span class="badge ' + cls + '">' + s + '</span>';
                }},
                { key: 'channel', label: 'Channel', sortable: true },
                { key: 'customerHandle', label: 'Customer', sortable: true },
                { key: 'stage', label: 'Stage', sortable: true, render: function(row) {
                    var s = row.stage || 'HANDOFF';
                    var cls = s === 'DISCOVER' ? 'badge-discover' : s === 'SUGGEST' ? 'badge-suggest' : s === 'CONFIRM' ? 'badge-confirm' : s === 'HANDOFF' ? 'badge-handoff' : 'badge-fulfilled';
                    return '<span class="badge ' + cls + '">' + s + '</span>';
                }},
            ],
            data: filteredData,
            onRowClick: function(row) {
                openLeadDrawer(row);
            },
            emptyMessage: 'No leads found'
        });

        // Select all checkbox
        var selectAll = document.getElementById('select-all');
        if (selectAll) {
            selectAll.addEventListener('change', function(e) {
                var checked = e.target.checked;
                filteredData.forEach(function(row) {
                    if (checked) selectedIds.add(row.id);
                    else selectedIds.delete(row.id);
                });
                document.querySelectorAll('.row-select').forEach(function(cb) {
                    cb.checked = checked;
                });
                updateBulkBar();
            });
        }

        // Row checkboxes
        document.querySelectorAll('.row-select').forEach(function(cb) {
            cb.addEventListener('change', function(e) {
                var id = parseInt(e.target.getAttribute('data-id'));
                if (e.target.checked) selectedIds.add(id);
                else selectedIds.delete(id);
                updateBulkBar();
            });
        });

        // Filter inputs
        ['filter-status', 'filter-stage', 'filter-from', 'filter-to'].forEach(function(id) {
            var el = document.getElementById(id);
            if (el) el.addEventListener('change', function() {
                renderLeadsTable(contentEl, allData);
            });
        });

        // Clear filters
        var clearBtn = document.getElementById('btn-clear-filters');
        if (clearBtn) {
            clearBtn.addEventListener('click', function() {
                document.getElementById('filter-status').value = '';
                document.getElementById('filter-stage').value = '';
                document.getElementById('filter-from').value = '';
                document.getElementById('filter-to').value = '';
                renderLeadsTable(contentEl, allData);
            });
        }

        // Bulk actions
        var bulkContacted = document.getElementById('bulk-contacted');
        if (bulkContacted) {
            bulkContacted.addEventListener('click', function() {
                bulkUpdateStatus('CONTACTED');
            });
        }

        var bulkClosed = document.getElementById('bulk-closed');
        if (bulkClosed) {
            bulkClosed.addEventListener('click', function() {
                bulkUpdateStatus('CLOSED');
            });
        }
    }

    function openLeadDrawer(lead) {
        var status = lead.status || 'NEW';

        var html = '' +
            '<div class="drawer-section">' +
            '<h4>Lead Info</h4>' +
            '<p><strong>ID:</strong> ' + lead.id + '</p>' +
            '<p><strong>Channel:</strong> ' + (lead.channel || '-') + '</p>' +
            '<p><strong>Customer:</strong> ' + (lead.customerHandle || '-') + '</p>' +
            '<p><strong>Created:</strong> ' + (lead.createdAt ? new Date(lead.createdAt).toLocaleString() : '-') + '</p>' +
            '<p><strong>Status:</strong> <span class="badge ' + statusBadgeClass(status) + '">' + status + '</span></p>' +
            '</div>' +
            '<div class="drawer-section">' +
            '<h4>Conversation</h4>' +
            renderConversationPanel(lead.transcript) +
            '</div>' +
            '<div class="drawer-section">' +
            '<h4>Slots</h4>' +
            '<pre class="pre">' + escapeHtml(lead.slotsJson || '{}') + '</pre>' +
            '</div>' +
            '<div class="drawer-section">' +
            '<h4>Actions</h4>' +
            '<button class="btn btn-secondary" id="btn-status-contacted">Mark Contacted</button>' +
            '<button class="btn btn-secondary" id="btn-false-signal">False signal</button>' +
            '<button class="btn btn-primary" id="btn-convert-pr">Convert to purchase request</button>' +
            '<button class="btn btn-secondary" id="btn-status-closed">Close lead</button>' +
            '</div>';

        var body = window.openDrawer('Lead Details', html);

        body.querySelector('#btn-send-reply').addEventListener('click', function() {
            var msg = body.querySelector('#drawer-reply-text').value.trim();
            if (!msg) return;
            window.api.post('/tenant/api/reply?tid=' + encodeURIComponent(tenantId), { leadId: lead.id, message: msg })
                .then(function() {
                    window.showToast('Reply sent', 'success');
                    appendStoreMessage(body, msg);
                    body.querySelector('#drawer-reply-text').value = '';
                    body.querySelector('#reply-status').textContent = 'Sent';
                })
                .catch(function(err) {
                    window.showToast('Failed: ' + err.message, 'error');
                });
        });

        body.querySelector('#btn-status-contacted').addEventListener('click', function() {
            window.api.post('/tenant/api/leads/' + lead.id + '/status?status=CONTACTED&tid=' + encodeURIComponent(tenantId))
                .then(function() {
                    window.showToast('Marked as CONTACTED', 'success');
                    window.closeDrawer();
                    render(container, params);
                })
                .catch(function(err) {
                    window.showToast('Failed: ' + err.message, 'error');
                });
        });

        body.querySelector('#btn-false-signal').addEventListener('click', function() {
            window.api.post('/tenant/api/leads/' + lead.id + '/status?status=FALSE_SIGNAL&tid=' + encodeURIComponent(tenantId))
                .then(function() {
                    window.showToast('Marked as false signal', 'success');
                    window.closeDrawer();
                    render(container, params);
                })
                .catch(function(err) {
                    window.showToast('Failed: ' + err.message, 'error');
                });
        });

        body.querySelector('#btn-convert-pr').addEventListener('click', function() {
            window.api.post('/tenant/api/leads-ops/' + lead.id + '/convert-purchase-request?tid=' + encodeURIComponent(tenantId))
                .then(function(pr) {
                    window.showToast('Created purchase request #' + pr.id, 'success');
                    window.closeDrawer();
                    window.location.hash = '#/purchase-requests';
                })
                .catch(function(err) {
                    window.showToast('Failed: ' + err.message, 'error');
                });
        });

        body.querySelector('#btn-status-closed').addEventListener('click', function() {
            window.api.post('/tenant/api/leads/' + lead.id + '/status?status=CLOSED&tid=' + encodeURIComponent(tenantId))
                .then(function() {
                    window.showToast('Marked as CLOSED', 'success');
                    window.closeDrawer();
                    render(container, params);
                })
                .catch(function(err) {
                    window.showToast('Failed: ' + err.message, 'error');
                });
        });
    }

    function escapeHtml(value) {
        return String(value == null ? '' : value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function statusBadgeClass(status) {
        var s = status || 'NEW';
        if (s === 'NEW') return 'badge-new';
        if (s === 'CONTACTED') return 'badge-contacted';
        if (s === 'CONVERTED') return 'badge-converted';
        if (s === 'FALSE_SIGNAL') return 'badge-false-signal';
        return 'badge-closed';
    }

    function renderConversation(transcript) {
        var messages = parseTranscript(transcript || '');
        if (!messages.length) {
            return '<div class="conversation-chat conversation-empty">No transcript</div>';
        }

        var html = '<div class="conversation-chat" aria-label="Conversation transcript">';
        messages.forEach(function(message) {
            var isStore = message.role === 'assistant';
            html += '' +
                '<div class="chat-row ' + (isStore ? 'chat-row-store' : 'chat-row-customer') + '">' +
                '<div class="chat-bubble ' + (isStore ? 'chat-bubble-store' : 'chat-bubble-customer') + '">' +
                '<div class="chat-sender">' + (isStore ? 'Cửa hàng' : 'Khách hàng') + '</div>' +
                '<div class="chat-message">' + escapeHtml(formatChatText(message.text)) + '</div>' +
                '</div>' +
                '</div>';
        });
        html += '</div>';
        return html;
    }

    function renderConversationPanel(transcript) {
        return '<div class="chat-panel">' +
            renderConversation(transcript) +
            '<div class="chat-composer">' +
            '<textarea id="drawer-reply-text" class="form-input" placeholder="Type a message to customer..."></textarea>' +
            '<div class="chat-composer-actions">' +
            '<span class="muted" id="reply-status"></span>' +
            '<button class="btn btn-primary" id="btn-send-reply">Send</button>' +
            '</div>' +
            '</div>' +
            '</div>';
    }

    function appendStoreMessage(body, text) {
        var chat = body.querySelector('.conversation-chat');
        if (!chat || chat.classList.contains('conversation-empty')) return;
        chat.insertAdjacentHTML('beforeend',
            '<div class="chat-row chat-row-store">' +
            '<div class="chat-bubble chat-bubble-store">' +
            '<div class="chat-sender">Cua hang</div>' +
            '<div class="chat-message">' + escapeHtml(text) + '</div>' +
            '</div>' +
            '</div>'
        );
        chat.scrollTop = chat.scrollHeight;
    }

    function formatChatText(text) {
        return String(text == null ? '' : text)
            .replace(/\r\n/g, '\n')
            .replace(/[ \t]+/g, ' ')
            .replace(/\s+(?=\d+\.\s+\S)/g, '\n\n')
            .replace(/\s+-\s+(?=(Gi[aá]|Danh mục|Ph[uù] hợp|Thuộc tính|SKU|Trạng thái|Link|Nguồn|Mã sản phẩm))/gi, '\n- ')
            .replace(/\s+(?=https?:\/\/)/g, '\n')
            .replace(/\s+(?=(Lưu ý|Luu y):)/gi, '\n\n')
            .replace(/\n{3,}/g, '\n\n')
            .trim();
    }

    function parseTranscript(transcript) {
        var messages = [];
        String(transcript || '').split(/\r?\n/).forEach(function(line) {
            var trimmed = line.trim();
            var match;
            if (!trimmed) return;

            match = trimmed.match(/^(user|customer|kh[aá]ch(?: hàng)?):\s*(.*)$/i);
            if (match) {
                messages.push({ role: 'user', text: match[2] || '' });
                return;
            }

            match = trimmed.match(/^(assistant|bot|chatbot|store|shop|c[uử]a hàng):\s*(.*)$/i);
            if (match) {
                messages.push({ role: 'assistant', text: match[2] || '' });
                return;
            }

            if (messages.length) {
                messages[messages.length - 1].text += '\n' + trimmed;
            } else {
                messages.push({ role: 'assistant', text: trimmed });
            }
        });

        return messages.filter(function(message) {
            return message.text.trim().length > 0;
        });
    }
}
