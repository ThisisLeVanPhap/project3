(function() {
    'use strict';

    function formatDate(d) {
        if (!d) return '-';
        var date = new Date(d);
        var dd = String(date.getDate()).padStart(2, '0');
        var mm = String(date.getMonth() + 1).padStart(2, '0');
        var hh = String(date.getHours()).padStart(2, '0');
        var mi = String(date.getMinutes()).padStart(2, '0');
        return dd + '/' + mm + ' ' + hh + ':' + mi;
    }

    function escapeHtml(s) {
        if (!s) return '';
        return String(s).replace(/[&<>"']/g, function(c) {
            return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
        });
    }

    function statusBadge(s) {
        s = (s || 'NEW').toUpperCase();
        var cls = s === 'NEW' ? 'badge-pr-new' : s === 'CONTACTED' ? 'badge-pr-contacted' : 'badge-pr-completed';
        return '<span class="badge ' + cls + '">' + s + '</span>';
    }

    function openPurchaseRequestDetail(pr) {
        var tenantId = localStorage.getItem('tenant_id') || '';

        var html = '<div class="pr-tabs">' +
            '<div class="tab-nav">' +
            '<button class="tab-btn active" data-tab="details">Details</button>' +
            '<button class="tab-btn" data-tab="notes">Notes</button>' +
            '<button class="tab-btn" data-tab="actions">Actions</button>' +
            '</div>' +
            '<div class="tab-content">' +
            '<div class="tab-pane active" data-pane="details">' +
            '<div class="info-grid" id="pr-info-grid">' +
            '<div class="info-field"><label>Product</label><div>' + escapeHtml(pr.requestedProductRef || pr.productName || '-') + '</div></div>' +
            '<div class="info-field"><label>Status</label><div>' + statusBadge(pr.status) + '</div></div>' +
            '<div class="info-field"><label>Customer</label><div>' + escapeHtml(pr.customerName || '-') + '</div></div>' +
            '<div class="info-field"><label>Phone</label><div>' + escapeHtml(pr.phone || pr.customerPhone || '-') + '</div></div>' +
            '<div class="info-field" style="grid-column: 1/-1;"><label>Address</label><div>' + escapeHtml(pr.shippingAddress || pr.customerAddress || '-') + '</div></div>' +
            '<div class="info-field"><label>Notes</label><div>' + escapeHtml(pr.notes || '-') + '</div></div>' +
            '<div class="info-field"><label>Assigned to</label><div>' + escapeHtml(pr.assignedToDisplayName || pr.assignedTo || 'Unassigned') + '</div></div>' +
            '<div class="info-field"><label>Created</label><div>' + formatDate(pr.createdAt) + '</div></div>' +
            '<div class="info-field"><label>Lead ID</label><div class="mono">' + (pr.leadId || '-') + '</div></div>' +
            '</div>' +
            '<div style="margin-top: 16px;"><button class="btn btn-secondary" id="btn-edit-buyer-info">Edit buyer info</button></div>' +
            '</div>' +
            '<div class="tab-pane" data-pane="notes">' +
            '<div class="notes-section">' +
            '<div class="notes-list" id="pr-notes-list"><p class="muted">Loading notes...</p></div>' +
            '<div class="note-input">' +
            '<textarea id="pr-note-text" placeholder="Add a note..."></textarea>' +
            '<button class="btn btn-primary" id="btn-add-pr-note">Add note</button>' +
            '</div></div></div>' +
            '<div class="tab-pane" data-pane="actions">' +
            '<div class="actions-section">' +
            '<div class="action-group"><h4>Assignment</h4>';

        var currentEmail = (window.CURRENT_PRINCIPAL || {}).email || '';
        var assignedTo = pr.assignedToDisplayName || pr.assignedTo;
        if (!assignedTo) {
            html += '<button class="btn btn-primary" id="btn-pr-claim">Claim this PR</button>' +
                '<p class="muted">Assign to yourself to start working on this order.</p>';
        } else {
            html += '<p>Assigned to: <strong>' + escapeHtml(assignedTo) + '</strong></p>';
            if (assignedTo === currentEmail) {
                html += '<button class="btn btn-secondary" id="btn-pr-unclaim" disabled title="Coming soon">Release assignment</button>';
            }
        }
        html += '</div><div class="action-group"><h4>Status</h4>';

        var st = (pr.status || 'NEW').toUpperCase();
        html += '<button class="btn btn-secondary" id="btn-pr-contacted"' + (st === 'CONTACTED' || st === 'COMPLETED' ? ' disabled' : '') + '>Mark Contacted</button>';
        html += '<button class="btn btn-secondary" id="btn-pr-completed"' + (st === 'COMPLETED' ? ' disabled' : '') + '>Mark Completed</button>';
        html += '</div></div></div></div></div>';

        var body = window.openDrawer('Purchase Request #' + pr.id, html);

        body.querySelectorAll('.tab-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                body.querySelectorAll('.tab-btn').forEach(function(b) { b.classList.remove('active'); });
                body.querySelectorAll('.tab-pane').forEach(function(p) { p.classList.remove('active'); });
                btn.classList.add('active');
                body.querySelector('[data-pane="' + btn.getAttribute('data-tab') + '"]').classList.add('active');
            });
        });

        loadNotes(pr.id, body);

        var addBtn = body.querySelector('#btn-add-pr-note');
        if (addBtn) {
            addBtn.addEventListener('click', function() {
                var text = body.querySelector('#pr-note-text').value.trim();
                if (!text) return;
                window.api.post('/tenant/api/purchase-requests/' + pr.id + '/note?tid=' + encodeURIComponent(tenantId), { text: text })
                    .then(function() {
                        window.showToast('Note added', 'success');
                        body.querySelector('#pr-note-text').value = '';
                        loadNotes(pr.id, body);
                    })
                    .catch(function(err) { window.showToast('Failed: ' + err.message, 'error'); });
            });
        }

        function reloadParent() {
            if (window.__prReload) window.__prReload();
        }

        var editBtn = body.querySelector('#btn-edit-buyer-info');
        if (editBtn) {
            editBtn.addEventListener('click', function() {
                openEditBuyerInfoForm(pr, body);
            });
        }

        var claimBtn = body.querySelector('#btn-pr-claim');
        if (claimBtn) {
            claimBtn.addEventListener('click', function() {
                window.api.post('/tenant/api/purchase-requests/' + pr.id + '/claim?tid=' + encodeURIComponent(tenantId), {})
                    .then(function() {
                        window.showToast('Claimed successfully', 'success');
                        window.closeDrawer();
                        reloadParent();
                    })
                    .catch(function(err) { window.showToast('Failed: ' + err.message, 'error'); });
            });
        }

        var contactedBtn = body.querySelector('#btn-pr-contacted');
        if (contactedBtn) {
            contactedBtn.addEventListener('click', function() {
                window.api.post('/tenant/api/purchase-requests/' + pr.id + '/status?tid=' + encodeURIComponent(tenantId) + '&status=CONTACTED')
                    .then(function() {
                        window.showToast('Marked CONTACTED', 'success');
                        window.closeDrawer();
                        reloadParent();
                    })
                    .catch(function(err) { window.showToast('Failed: ' + err.message, 'error'); });
            });
        }

        var completedBtn = body.querySelector('#btn-pr-completed');
        if (completedBtn) {
            completedBtn.addEventListener('click', function() {
                window.api.post('/tenant/api/purchase-requests/' + pr.id + '/status?tid=' + encodeURIComponent(tenantId) + '&status=COMPLETED')
                    .then(function() {
                        window.showToast('Marked COMPLETED', 'success');
                        window.closeDrawer();
                        reloadParent();
                    })
                    .catch(function(err) { window.showToast('Failed: ' + err.message, 'error'); });
            });
        }
    }

    function openEditBuyerInfoForm(pr, body) {
        var tenantId = localStorage.getItem('tenant_id') || '';
        var pane = body.querySelector('[data-pane="details"]');
        if (!pane) return;

        pane.innerHTML = '<div class="edit-form">' +
            '<h4>Edit Buyer Info</h4>' +
            '<label>Customer name</label>' +
            '<input type="text" id="edit-customer-name" value="' + escapeHtml(pr.customerName || '') + '">' +
            '<label>Phone</label>' +
            '<input type="text" id="edit-phone" value="' + escapeHtml(pr.phone || pr.customerPhone || '') + '">' +
            '<label>Shipping address</label>' +
            '<textarea id="edit-address">' + escapeHtml(pr.shippingAddress || pr.customerAddress || '') + '</textarea>' +
            '<label>Notes</label>' +
            '<textarea id="edit-notes">' + escapeHtml(pr.notes || '') + '</textarea>' +
            '<label>Product reference</label>' +
            '<input type="text" id="edit-product" value="' + escapeHtml(pr.requestedProductRef || pr.productName || '') + '">' +
            '<div class="form-actions">' +
            '<button class="btn btn-primary" id="btn-save-edit">Save</button>' +
            '<button class="btn btn-secondary" id="btn-cancel-edit">Cancel</button>' +
            '</div></div>';

        pane.querySelector('#btn-save-edit').addEventListener('click', function() {
            var payload = {
                customerName: pane.querySelector('#edit-customer-name').value,
                phone: pane.querySelector('#edit-phone').value,
                shippingAddress: pane.querySelector('#edit-address').value,
                notes: pane.querySelector('#edit-notes').value,
                requestedProductRef: pane.querySelector('#edit-product').value
            };

            window.api.put('/api/purchase-requests/' + pr.id, payload)
                .then(function() {
                    window.showToast('Updated successfully', 'success');
                    window.closeDrawer();
                    if (window.__prReload) window.__prReload();
                })
                .catch(function(err) {
                    window.showToast('Failed: ' + err.message, 'error');
                });
        });

        pane.querySelector('#btn-cancel-edit').addEventListener('click', function() {
            openPurchaseRequestDetail(pr);
        });
    }

    function loadNotes(prId, body) {
        var tenantId = localStorage.getItem('tenant_id') || '';
        var listEl = body.querySelector('#pr-notes-list');
        if (!listEl) return;
        window.api.get('/tenant/api/purchase-requests/' + prId + '/notes?tid=' + encodeURIComponent(tenantId))
            .then(function(notes) {
                if (!notes || !notes.length) {
                    listEl.innerHTML = '<p class="muted">No notes yet.</p>';
                    return;
                }
                function relativeTime(d) {
                    if (!d) return '-';
                    var diff = Date.now() - new Date(d).getTime();
                    var mins = Math.floor(diff / 60000);
                    if (mins < 1) return 'now';
                    if (mins < 60) return mins + 'm';
                    var hours = Math.floor(mins / 60);
                    if (hours < 24) return hours + 'h';
                    var days = Math.floor(hours / 24);
                    if (days < 7) return days + 'd';
                    return Math.floor(days / 7) + 'w';
                }
                listEl.innerHTML = notes.map(function(n) {
                    return '<div class="note-item">' +
                        '<div class="note-header">' +
                        '<span class="note-author">' + escapeHtml(n.author || 'Unknown') + '</span>' +
                        '<span class="note-time">' + relativeTime(n.createdAt) + '</span>' +
                        '</div>' +
                        '<div class="note-text">' + escapeHtml(n.text || '') + '</div>' +
                        '</div>';
                }).join('');
            })
            .catch(function() {
                listEl.innerHTML = '<p class="muted">Failed to load notes.</p>';
            });
    }

    window.openPurchaseRequestDetail = openPurchaseRequestDetail;
})();
