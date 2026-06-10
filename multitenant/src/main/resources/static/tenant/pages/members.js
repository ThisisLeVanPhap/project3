export async function render(container, params) {
    container.innerHTML = '' +
        '<div class="page">' +
        '<h1>Members</h1>' +
        '<p class="subtitle">Manage tenant staff accounts</p>' +
        '<div class="toolbar">' +
        '<button class="btn btn-primary" id="btn-create-member">+ New Member</button>' +
        '</div>' +
        '<div id="members-content"></div>' +
        '</div>';

    var contentEl = container.querySelector('#members-content');

    loadMembers();

    container.querySelector('#btn-create-member').addEventListener('click', function() {
        openMemberDrawer(null);
    });

    async function loadMembers() {
        contentEl.innerHTML = '<div class="skeleton-container">' +
            '<div class="skeleton skeleton-title"></div>' +
            '<div class="skeleton skeleton-card"></div>' +
            '<div class="skeleton skeleton-card"></div>' +
            '</div>';
        try {
            var members = await window.api.get('/api/tenant-members');
            renderTable(contentEl, members);
        } catch (err) {
            contentEl.innerHTML = '<div class="placeholder-card"><p>Failed to load: ' + err.message + '</p></div>';
        }
    }

    function renderTable(el, data) {
        if (!data || !data.length) {
            el.innerHTML = '<div class="empty-state">' +
                '<div class="icon">👥</div>' +
                '<div class="title">No members yet</div>' +
                '<div class="description">Add team members to collaborate on leads and purchase requests.</div>' +
                '</div>';
            return;
        }

        window.createTable(el, {
            columns: [
                { key: 'email', label: 'Email', sortable: true },
                { key: 'displayName', label: 'Display Name', sortable: true },
                { key: 'role', label: 'Role', sortable: true, render: function(row) {
                    return '<span class="badge badge-role-' + (row.role || '').toLowerCase().replace('_', '-') + '">' + (row.role || '-') + '</span>';
                }},
                { key: 'status', label: 'Status', sortable: true, render: function(row) {
                    var s = row.status || 'ACTIVE';
                    var cls = s === 'ACTIVE' ? 'badge-status-active' : 'badge-status-inactive';
                    return '<span class="badge ' + cls + '">' + s + '</span>';
                }},
                { key: 'createdAt', label: 'Created', sortable: true, render: function(row) {
                    return row.createdAt ? new Date(row.createdAt).toLocaleDateString() : '-';
                }}
            ],
            data: data,
            onRowClick: function(row) {
                openMemberDrawer(row);
            },
            emptyMessage: 'No members found'
        });
    }

    function openMemberDrawer(member) {
        var isEdit = !!member;
        var title = isEdit ? 'Edit Member' : 'Create Member';

        var html = '' +
            '<div class="drawer-section">' +
            '<h4>Account Info</h4>' +
            '<label>Email</label>' +
            '<input type="email" class="form-input" id="member-email" value="' + (member ? member.email : '') + '" ' + (isEdit ? 'disabled' : '') + '>' +
            '<label style="margin-top: 12px;">Display Name</label>' +
            '<input type="text" class="form-input" id="member-display-name" value="' + (member ? (member.displayName || '') : '') + '">' +
            '<label style="margin-top: 12px;">Role</label>' +
            '<select class="form-input" id="member-role">' +
            '<option value="TENANT_MEMBER"' + (member && member.role === 'TENANT_MEMBER' ? ' selected' : '') + '>TENANT_MEMBER</option>' +
            '<option value="TENANT_ADMIN"' + (member && member.role === 'TENANT_ADMIN' ? ' selected' : '') + '>TENANT_ADMIN</option>' +
            '</select>' +
            (isEdit ? '' : '<label style="margin-top: 12px;">Password</label><input type="password" class="form-input" id="member-password" placeholder="Required for new member">') +
            (isEdit ? '<label style="margin-top: 12px;">Status</label><select class="form-input" id="member-status"><option value="ACTIVE"' + (member.status === 'ACTIVE' ? ' selected' : '') + '>ACTIVE</option><option value="INACTIVE"' + (member.status === 'INACTIVE' ? ' selected' : '') + '>INACTIVE</option></select>' : '') +
            '</div>' +
            '<div class="drawer-section">' +
            '<button class="btn btn-primary" id="btn-save-member">' + (isEdit ? 'Update' : 'Create') + '</button>' +
            (isEdit ? '<button class="btn btn-secondary" id="btn-reset-password" style="margin-left: 8px;">Reset Password</button>' : '') +
            '</div>';

        var body = window.openDrawer(title, html);

        body.querySelector('#btn-save-member').addEventListener('click', function() {
            var email = body.querySelector('#member-email').value.trim();
            var displayName = body.querySelector('#member-display-name').value.trim();
            var role = body.querySelector('#member-role').value;

            if (!email) {
                window.showToast('Email is required', 'warning');
                return;
            }

            if (isEdit) {
                var status = body.querySelector('#member-status').value;
                window.api.put('/api/tenant-members/' + member.id, { displayName: displayName, role: role, status: status })
                    .then(function() {
                        window.showToast('Member updated', 'success');
                        window.closeDrawer();
                        loadMembers();
                    })
                    .catch(function(err) {
                        window.showToast('Failed: ' + err.message, 'error');
                    });
            } else {
                var password = body.querySelector('#member-password').value;
                if (!password) {
                    window.showToast('Password is required', 'warning');
                    return;
                }
                window.api.post('/api/tenant-members', { email: email, displayName: displayName, role: role, status: 'ACTIVE', password: password })
                    .then(function() {
                        window.showToast('Member created', 'success');
                        window.closeDrawer();
                        loadMembers();
                    })
                    .catch(function(err) {
                        window.showToast('Failed: ' + err.message, 'error');
                    });
            }
        });

        if (isEdit) {
            body.querySelector('#btn-reset-password').addEventListener('click', function() {
                var newPassword = prompt('Enter new password:');
                if (!newPassword) return;
                window.api.put('/api/tenant-members/' + member.id + '/password', { password: newPassword })
                    .then(function() {
                        window.showToast('Password reset', 'success');
                    })
                    .catch(function(err) {
                        window.showToast('Failed: ' + err.message, 'error');
                    });
            });
        }
    }
}
