export async function render(container, params) {
    var tenantId = localStorage.getItem('tenant_id') || '';
    var currentView = 'table';
    var allData = null;

    container.innerHTML = '' +
        '<div class="page">' +
        '<h1>Purchase Requests</h1>' +
        '<p class="subtitle">Orders extracted from confirmed leads</p>' +
        '<div class="view-toggle" id="view-toggle">' +
        '<button class="btn btn-secondary view-btn active" data-view="table">Table</button>' +
        '<button class="btn btn-secondary view-btn" data-view="kanban">Kanban</button>' +
        '</div>' +
        '<div class="toolbar" style="margin-top: 12px;">' +
        '<button class="btn btn-secondary" id="btn-export-csv">📥 Export CSV</button>' +
        '</div>' +
        '<div id="pr-content"></div>' +
        '</div>';

    var contentEl = container.querySelector('#pr-content');

    container.querySelectorAll('.view-btn').forEach(function(btn) {
        btn.addEventListener('click', function() {
            currentView = btn.getAttribute('data-view');
            container.querySelectorAll('.view-btn').forEach(function(b) { b.classList.remove('active'); });
            btn.classList.add('active');
            loadPurchaseRequests();
        });
    });

    var exportBtn = container.querySelector('#btn-export-csv');
    if (exportBtn) {
        exportBtn.addEventListener('click', function() {
            if (!allData || !allData.length) {
                if (window.showToast) window.showToast('No data to export', 'warning');
                return;
            }

            var headers = ['id','created_at','status','customer_name','phone','shipping_address','requested_product_ref','assigned_to_display_name'];
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
            a.download = 'purchase-requests-' + new Date().toISOString().slice(0,10) + '.csv';
            a.click();
            URL.revokeObjectURL(url);

            if (window.showToast) window.showToast('Exported ' + allData.length + ' purchase requests', 'success');
        });
    }

    loadPurchaseRequests();

    async function loadPurchaseRequests() {
        contentEl.innerHTML = '<div class="skeleton-container">' +
            '<div class="skeleton skeleton-title"></div>' +
            '<div class="skeleton skeleton-card"></div>' +
            '<div class="skeleton skeleton-card"></div>' +
            '</div>';
        try {
            var data = await window.api.get('/api/purchase-requests?tenantId=' + encodeURIComponent(tenantId));
            allData = data;
            if (currentView === 'table') {
                renderTable(contentEl, data);
            } else {
                renderKanban(contentEl, data);
            }
        } catch (err) {
            contentEl.innerHTML = '<div class="empty-state"><div class="icon">⚠️</div><div class="title">Failed to load</div><div class="description">' + err.message + '</div></div>';
        }
    }

    function renderTable(el, data) {
        if (!data || !data.length) {
            el.innerHTML = '<div class="empty-state">' +
                '<div class="icon">📦</div>' +
                '<div class="title">No purchase requests yet</div>' +
                '<div class="description">Purchase requests will appear here when customers confirm orders through the chatbot.</div>' +
                '</div>';
            return;
        }

        window.createTable(el, {
            columns: [
                { key: 'id', label: 'ID', sortable: true },
                { key: 'created_at', label: 'Created', sortable: true, render: function(row) {
                    return row.created_at ? new Date(row.created_at).toLocaleString() : '-';
                }},
                { key: 'status', label: 'Status', sortable: true, render: function(row) {
                    var s = normalizeStatus(row.status || 'NEW');
                    return '<span class="badge badge-pr-' + s.toLowerCase() + '">' + s + '</span>';
                }},
                { key: 'requested_product_ref', label: 'Product', sortable: true, render: function(row) {
                    return row.requested_product_ref || '-';
                }},
                { key: 'customer_name', label: 'Customer', sortable: true, render: function(row) {
                    return row.customer_name || '-';
                }},
                { key: 'phone', label: 'Phone', sortable: true, render: function(row) {
                    return row.phone || '-';
                }},
                { key: 'assigned_to_display_name', label: 'Assigned', sortable: true, render: function(row) {
                    return row.assigned_to_display_name || '—';
                }}
            ],
            data: data,
            onRowClick: function(row) {
                openPRDrawer(row);
            },
            emptyMessage: 'No purchase requests found'
        });
    }

    function renderKanban(el, data) {
        var columns = {
            'NEW': [],
            'PROCESSING': [],
            'COMPLETED': []
        };

        (data || []).forEach(function(pr) {
            var status = normalizeStatus(pr.status || 'NEW');
            if (columns[status]) columns[status].push(pr);
            else columns['NEW'].push(pr);
        });

        var html = '<div class="kanban-board">';
        Object.keys(columns).forEach(function(status) {
            var items = columns[status];
            html += '<div class="kanban-column" data-status="' + status + '">' +
                '<div class="kanban-column-header">' +
                '<span class="kanban-column-title">' + status + '</span>' +
                '<span class="kanban-column-count">' + items.length + '</span>' +
                '</div>' +
                '<div class="kanban-column-body">';

            if (items.length === 0) {
                html += '<div class="kanban-empty">No items</div>';
            } else {
                items.forEach(function(pr) {
                    html += '<div class="kanban-card" data-id="' + pr.id + '" draggable="true">' +
                        '<div class="kanban-card-title">' + (pr.customer_name || 'Unnamed') + '</div>' +
                        '<div class="kanban-card-meta">📞 ' + (pr.phone || '-') + '</div>' +
                        '<div class="kanban-card-meta">' + (pr.requested_product_ref || '-') + '</div>' +
                        '<div class="kanban-card-footer">' + (pr.assigned_to_display_name || 'Unassigned') + '</div>' +
                        '</div>';
                });
            }
            html += '</div></div>';
        });
        html += '</div>';

        el.innerHTML = html;

        // --- Drag-and-drop handlers ---
        var draggedId = null;
        var draggedStatus = null;

        el.querySelectorAll('.kanban-card[draggable]').forEach(function(card) {
            card.addEventListener('dragstart', function(e) {
                draggedId = card.getAttribute('data-id');
                draggedStatus = card.closest('.kanban-column').getAttribute('data-status');
                card.classList.add('dragging');
                e.dataTransfer.effectAllowed = 'move';
                e.dataTransfer.setData('text/plain', draggedId);
            });

            card.addEventListener('dragend', function() {
                card.classList.remove('dragging');
                el.querySelectorAll('.kanban-column').forEach(function(col) {
                    col.classList.remove('drag-over');
                });
            });
        });

        el.querySelectorAll('.kanban-column').forEach(function(column) {
            column.addEventListener('dragover', function(e) {
                e.preventDefault();
                e.dataTransfer.dropEffect = 'move';
                column.classList.add('drag-over');
            });

            column.addEventListener('dragleave', function(e) {
                if (!column.contains(e.relatedTarget)) {
                    column.classList.remove('drag-over');
                }
            });

            column.addEventListener('drop', function(e) {
                e.preventDefault();
                column.classList.remove('drag-over');
                var targetStatus = column.getAttribute('data-status');
                var cardId = e.dataTransfer.getData('text/plain');

                if (!cardId || !targetStatus || targetStatus === draggedStatus) return;

                var pr = (data || []).find(function(item) { return String(item.id) === String(cardId); });
                if (targetStatus === 'PROCESSING') {
                    if (draggedStatus === 'COMPLETED') {
                        window.showToast('Completed requests cannot be moved back to PROCESSING here', 'warning');
                        loadPurchaseRequests();
                        return;
                    }
                    var missing = missingProcessingFields(pr || {});
                    if (missing.length) {
                        window.showToast('Complete buyer details before processing: ' + missing.join(', '), 'warning');
                        loadPurchaseRequests();
                        return;
                    }
                }

                window.api.put('/api/purchase-requests/' + cardId + '/status', { status: targetStatus })
                    .then(function() {
                        window.showToast('Moved to ' + targetStatus, 'success');
                        loadPurchaseRequests();
                    })
                    .catch(function(err) {
                        window.showToast('Failed: ' + err.message, 'error');
                        loadPurchaseRequests();
                    });
            });
        });

        el.querySelectorAll('.kanban-card').forEach(function(card) {
            card.addEventListener('click', function() {
                var id = card.getAttribute('data-id');
                var pr = (data || []).find(function(p) { return String(p.id) === String(id); });
                if (pr) openPRDrawer(pr);
            });
        });
    }

    function openPRDrawer(pr) {
        var status = normalizeStatus(pr.status || 'NEW');
        var missing = missingProcessingFields(pr);
        var processingDisabled = status === 'PROCESSING' || status === 'COMPLETED' || missing.length > 0;
        var processingTitle = status === 'COMPLETED'
            ? 'Completed requests cannot be moved back to processing here'
            : status === 'PROCESSING'
                ? 'This request is already processing'
                : missing.length
                    ? 'Complete buyer details before processing: ' + missing.join(', ')
                    : '';
        var completedDisabled = status === 'COMPLETED';
        var transcript = pr.conversation_transcript || '';
        var html = '' +
            '<div class="drawer-section pr-summary">' +
            '<div class="pr-summary-head">' +
            '<div>' +
            '<div class="muted">Purchase request</div>' +
            '<h4>#' + escapeHtml(pr.id) + '</h4>' +
            '</div>' +
            '<span class="badge badge-pr-' + status.toLowerCase() + '">' + escapeHtml(status) + '</span>' +
            '</div>' +
            '<div class="pr-meta-grid">' +
            '<div><label>Created</label><strong>' + escapeHtml(pr.created_at ? new Date(pr.created_at).toLocaleString() : '-') + '</strong></div>' +
            '<div><label>Assigned</label><strong>' + escapeHtml(pr.assigned_to_display_name || 'Unassigned') + '</strong></div>' +
            '<div><label>Channel</label><strong>' + escapeHtml(pr.channel || '-') + '</strong></div>' +
            '<div><label>Source lead</label><strong>' + escapeHtml(pr.lead_id || '-') + '</strong></div>' +
            '</div>' +
            (missing.length ? '<div class="pr-alert">Missing before processing: ' + escapeHtml(missing.join(', ')) + '</div>' : '') +
            '</div>' +
            '<div class="drawer-section">' +
            '<h4>Buyer details</h4>' +
            '<div class="pr-detail-grid">' +
            fieldHtml('Customer', pr.customer_name) +
            fieldHtml('Phone', pr.phone) +
            fieldHtml('Delivery address', pr.shipping_address, true) +
            fieldHtml('Email', pr.email) +
            '</div>' +
            '</div>' +
            '<div class="drawer-section">' +
            '<h4>Purchase need</h4>' +
            '<div class="pr-detail-grid">' +
            fieldHtml('Product / SKU / URL', firstNonBlank(pr.requested_product_ref, pr.product_sku, pr.product_url), true) +
            fieldHtml('Quantity', pr.quantity) +
            fieldHtml('Price', pr.price) +
            fieldHtml('AI/customer context', pr.notes, true) +
            '</div>' +
            '</div>' +
            '<div class="drawer-section">' +
            '<h4>Conversation</h4>' +
            renderConversationPanel(transcript, !!pr.lead_id) +
            '</div>' +
            '<div class="drawer-section pr-actions">' +
            '<h4>Actions</h4>' +
            '<button class="btn btn-secondary" id="btn-edit">Edit buyer info</button>' +
            '<button class="btn btn-primary" id="btn-claim">Claim (assign to me)</button>' +
            '<button class="btn btn-secondary" id="btn-processing"' + (processingDisabled ? ' disabled' : '') + (processingTitle ? ' title="' + escapeHtml(processingTitle) + '"' : '') + '>Move to Processing</button>' +
            '<button class="btn btn-secondary" id="btn-completed"' + (completedDisabled ? ' disabled' : '') + '>Mark Completed</button>' +
            '</div>';

        var body = window.openDrawer('Purchase Request #' + pr.id, html);

        var sendBtn = body.querySelector('#btn-send-pr-reply');
        if (sendBtn) {
            sendBtn.addEventListener('click', function() {
                var input = body.querySelector('#pr-reply-text');
                var statusEl = body.querySelector('#pr-reply-status');
                var msg = input.value.trim();
                if (!msg) return;
                if (!pr.lead_id) {
                    window.showToast('This request is not linked to a lead conversation', 'error');
                    return;
                }
                window.api.post('/tenant/api/reply?tid=' + encodeURIComponent(tenantId), { leadId: pr.lead_id, message: msg })
                    .then(function() {
                        window.showToast('Reply sent', 'success');
                        appendStoreMessage(body, msg);
                        input.value = '';
                        statusEl.textContent = 'Sent';
                    })
                    .catch(function(err) {
                        window.showToast('Failed: ' + err.message, 'error');
                    });
            });
        }

        body.querySelector('#btn-edit').addEventListener('click', function() {
            openEditForm(pr, loadPurchaseRequests);
        });

        body.querySelector('#btn-claim').addEventListener('click', function() {
            window.api.put('/api/purchase-requests/' + pr.id + '/claim', {})
                .then(function() {
                    window.showToast('Claimed successfully', 'success');
                    window.closeDrawer();
                    loadPurchaseRequests();
                })
                .catch(function(err) {
                    window.showToast('Failed: ' + err.message, 'error');
                });
        });

        body.querySelector('#btn-processing').addEventListener('click', function() {
            window.api.put('/api/purchase-requests/' + pr.id + '/status', { status: 'PROCESSING' })
                .then(function() {
                    window.showToast('Moved to PROCESSING', 'success');
                    window.closeDrawer();
                    loadPurchaseRequests();
                })
                .catch(function(err) {
                    window.showToast('Failed: ' + err.message, 'error');
                });
        });

        body.querySelector('#btn-completed').addEventListener('click', function() {
            window.api.put('/api/purchase-requests/' + pr.id + '/status', { status: 'COMPLETED' })
                .then(function() {
                    window.showToast('Marked COMPLETED', 'success');
                    window.closeDrawer();
                    loadPurchaseRequests();
                })
                .catch(function(err) {
                    window.showToast('Failed: ' + err.message, 'error');
                });
        });
    }

    function openEditForm(pr, onSaved) {
        var html = '' +
            '<div class="edit-form">' +
            '<label>Customer name</label>' +
            '<input type="text" id="edit-name" value="' + (pr.customer_name || '') + '">' +
            '<label>Phone</label>' +
            '<input type="text" id="edit-phone" value="' + (pr.phone || '') + '">' +
            '<label>Shipping address</label>' +
            '<textarea id="edit-address">' + (pr.shipping_address || '') + '</textarea>' +
            '<label>Notes</label>' +
            '<textarea id="edit-notes">' + (pr.notes || '') + '</textarea>' +
            '<label>Product reference</label>' +
            '<input type="text" id="edit-product" value="' + (pr.requested_product_ref || '') + '">' +
            '<div class="form-actions">' +
            '<button class="btn btn-primary" id="btn-save-edit">Save</button>' +
            '<button class="btn btn-secondary" id="btn-cancel-edit">Cancel</button>' +
            '</div>' +
            '</div>';

        var body = document.querySelector('.drawer-body');
        body.innerHTML = html;

        body.querySelector('#btn-save-edit').addEventListener('click', function() {
            var payload = {
                customerName: body.querySelector('#edit-name').value,
                phone: body.querySelector('#edit-phone').value,
                shippingAddress: body.querySelector('#edit-address').value,
                notes: body.querySelector('#edit-notes').value,
                requestedProductRef: body.querySelector('#edit-product').value
            };

            window.api.put('/api/purchase-requests/' + pr.id, payload)
                .then(function() {
                    window.showToast('Updated successfully', 'success');
                    window.closeDrawer();
                    if (onSaved) onSaved();
                })
                .catch(function(err) {
                    window.showToast('Failed: ' + err.message, 'error');
                });
        });

        body.querySelector('#btn-cancel-edit').addEventListener('click', function() {
            openPRDrawer(pr);
        });
    }

    function normalizeStatus(status) {
        var s = (status || 'NEW').toUpperCase();
        return s === 'CONTACTED' ? 'PROCESSING' : s;
    }

    function escapeHtml(value) {
        return String(value == null ? '' : value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function firstNonBlank() {
        for (var i = 0; i < arguments.length; i++) {
            var value = arguments[i];
            if (value != null && String(value).trim()) return value;
        }
        return '';
    }

    function fieldHtml(label, value, wide) {
        var text = firstNonBlank(value, '-');
        return '<div class="pr-field ' + (wide ? 'pr-field-wide' : '') + '">' +
            '<label>' + escapeHtml(label) + '</label>' +
            '<div>' + escapeHtml(text) + '</div>' +
            '</div>';
    }

    function missingProcessingFields(pr) {
        var missing = [];
        if (!firstNonBlank(pr.customer_name)) missing.push('customer name');
        var phone = firstNonBlank(pr.phone);
        if (!phone) missing.push('phone');
        else if (!isValidVietnamPhone(phone)) missing.push('valid phone');
        if (!firstNonBlank(pr.shipping_address)) missing.push('delivery address');
        return missing;
    }

    function isValidVietnamPhone(phone) {
        var digits = String(phone || '').replace(/[^\d+]/g, '').replace(/^\+/, '');
        return /^(0[3-9]\d{8}|84[3-9]\d{8})$/.test(digits);
    }

    function renderConversationPanel(transcript, canReply) {
        var html = renderConversation(transcript);
        html += '<div class="chat-composer">' +
            '<textarea id="pr-reply-text" class="form-input" placeholder="' + (canReply ? 'Type a message to customer...' : 'No linked lead conversation for replies') + '"' + (canReply ? '' : ' disabled') + '></textarea>' +
            '<div class="chat-composer-actions">' +
            '<span class="muted" id="pr-reply-status">' + (canReply ? '' : 'Reply unavailable') + '</span>' +
            '<button class="btn btn-primary" id="btn-send-pr-reply"' + (canReply ? '' : ' disabled') + '>Send</button>' +
            '</div>' +
            '</div>';
        return '<div class="chat-panel">' + html + '</div>';
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
                '<div class="chat-sender">' + (isStore ? 'Store' : 'Customer') + '</div>' +
                '<div class="chat-message">' + escapeHtml(formatChatText(message.text)) + '</div>' +
                '</div>' +
                '</div>';
        });
        html += '</div>';
        return html;
    }

    function appendStoreMessage(body, text) {
        var chat = body.querySelector('.conversation-chat');
        if (!chat || chat.classList.contains('conversation-empty')) return;
        chat.insertAdjacentHTML('beforeend',
            '<div class="chat-row chat-row-store">' +
            '<div class="chat-bubble chat-bubble-store">' +
            '<div class="chat-sender">Store</div>' +
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
