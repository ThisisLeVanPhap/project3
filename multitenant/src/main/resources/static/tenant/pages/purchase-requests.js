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
                    var s = row.status || 'NEW';
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
            'CONTACTED': [],
            'COMPLETED': []
        };

        (data || []).forEach(function(pr) {
            var status = pr.status || 'NEW';
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
        var html = '' +
            '<div class="drawer-section">' +
            '<h4>Request Info</h4>' +
            '<p><strong>ID:</strong> ' + pr.id + '</p>' +
            '<p><strong>Status:</strong> <span class="badge badge-pr-' + (pr.status || 'new').toLowerCase() + '">' + (pr.status || 'NEW') + '</span></p>' +
            '<p><strong>Customer:</strong> ' + (pr.customer_name || '-') + '</p>' +
            '<p><strong>Phone:</strong> ' + (pr.phone || '-') + '</p>' +
            '<p><strong>Address:</strong> ' + (pr.shipping_address || '-') + '</p>' +
            '<p><strong>Product:</strong> ' + (pr.requested_product_ref || '-') + '</p>' +
            '<p><strong>Notes:</strong> ' + (pr.notes || '-') + '</p>' +
            '<p><strong>Created:</strong> ' + (pr.created_at ? new Date(pr.created_at).toLocaleString() : '-') + '</p>' +
            '<p><strong>Assigned:</strong> ' + (pr.assigned_to_display_name || 'Unassigned') + '</p>' +
            '</div>' +
            '<div class="drawer-section">' +
            '<h4>Actions</h4>' +
            '<button class="btn btn-secondary" id="btn-edit">Edit buyer info</button>' +
            '<button class="btn btn-primary" id="btn-claim">Claim (assign to me)</button>' +
            '<button class="btn btn-secondary" id="btn-contacted">Mark Contacted</button>' +
            '<button class="btn btn-secondary" id="btn-completed">Mark Completed</button>' +
            '</div>';

        var body = window.openDrawer('Purchase Request #' + pr.id, html);

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

        body.querySelector('#btn-contacted').addEventListener('click', function() {
            window.api.put('/api/purchase-requests/' + pr.id + '/status', { status: 'CONTACTED' })
                .then(function() {
                    window.showToast('Marked CONTACTED', 'success');
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
}
