export async function render(container, params) {
    container.innerHTML = '' +
        '<div class="page">' +
        '<h1>Channel Bindings</h1>' +
        '<p class="subtitle">Telegram and Messenger integrations</p>' +
        '<div id="bindings-content"></div>' +
        '</div>';

    var contentEl = container.querySelector('#bindings-content');

    loadAll();

    async function loadAll() {
        contentEl.innerHTML = '<div class="skeleton-container">' +
            '<div class="skeleton skeleton-title"></div>' +
            '<div class="skeleton skeleton-card"></div>' +
            '<div class="skeleton skeleton-card"></div>' +
            '</div>';
        try {
            var results = await Promise.all([
                window.api.get('/api/telegram/bindings').catch(function() { return []; }),
                window.api.get('/api/messenger/bindings').catch(function() { return []; })
            ]);
            renderBindings(contentEl, results[0], results[1]);
        } catch (err) {
            contentEl.innerHTML = '<div class="placeholder-card"><p>Failed to load: ' + err.message + '</p></div>';
        }
    }

    function renderBindings(el, telegram, messenger) {
        var html = '';

        html += '<div class="bindings-section">' +
            '<h3>Telegram</h3>' +
            '<div class="toolbar">' +
            '<button class="btn btn-primary" id="btn-add-telegram">+ Add Telegram Binding</button>' +
            '</div>' +
            '<div id="telegram-table"></div>' +
            '</div>';

        html += '<div class="bindings-section">' +
            '<h3>Messenger</h3>' +
            '<div class="toolbar">' +
            '<button class="btn btn-primary" id="btn-add-messenger">+ Add Messenger Binding</button>' +
            '</div>' +
            '<div id="messenger-table"></div>' +
            '</div>';

        el.innerHTML = html;

        renderChannelTable(el.querySelector('#telegram-table'), telegram, 'telegram');
        renderChannelTable(el.querySelector('#messenger-table'), messenger, 'messenger');

        el.querySelector('#btn-add-telegram').addEventListener('click', function() {
            openBindingDrawer('telegram', null);
        });
        el.querySelector('#btn-add-messenger').addEventListener('click', function() {
            openBindingDrawer('messenger', null);
        });
    }

    function renderChannelTable(containerEl, data, channel) {
        if (!data || !data.length) {
            var icon = channel === 'telegram' ? '📱' : '💬';
            var channelLabel = channel.charAt(0).toUpperCase() + channel.slice(1);
            var desc = channel === 'telegram'
                ? 'Connect a Telegram bot to receive messages from customers.'
                : 'Connect a Facebook Page to receive messages from customers.';
            containerEl.innerHTML = '<div class="empty-state">' +
                '<div class="icon">' + icon + '</div>' +
                '<div class="title">No ' + channelLabel + ' bindings</div>' +
                '<div class="description">' + desc + '</div>' +
                '</div>';
            return;
        }

        window.createTable(containerEl, {
            columns: [
                { key: 'chatId', label: 'Chat ID', sortable: true },
                { key: 'botName', label: 'Bot', sortable: true },
                { key: 'enabled', label: 'Enabled', sortable: true, render: function(row) {
                    return row.enabled !== false ? '<span class="badge badge-status-active">ON</span>' : '<span class="badge badge-status-inactive">OFF</span>';
                }},
                { key: 'createdAt', label: 'Created', sortable: true, render: function(row) {
                    return row.createdAt ? new Date(row.createdAt).toLocaleDateString() : '-';
                }}
            ],
            data: data,
            onRowClick: function(row) {
                openBindingDrawer(channel, row);
            },
            emptyMessage: 'No bindings'
        });
    }

    function openBindingDrawer(channel, binding) {
        var isEdit = !!binding;
        var channelLabel = channel.charAt(0).toUpperCase() + channel.slice(1);
        var title = isEdit ? 'Edit ' + channelLabel + ' Binding' : 'New ' + channelLabel + ' Binding';

        var html = '' +
            '<div class="drawer-section">' +
            '<h4>Configuration</h4>' +
            '<label>Chat ID / Page ID</label>' +
            '<input type="text" class="form-input" id="binding-chat-id" value="' + (binding ? (binding.chatId || '') : '') + '" placeholder="e.g. -1001234567890">' +
            '<label style="margin-top: 12px;">Bot Name</label>' +
            '<input type="text" class="form-input" id="binding-bot-name" value="' + (binding ? (binding.botName || '') : '') + '" placeholder="e.g. Sales Bot">' +
            (isEdit ? '<label style="margin-top: 12px;"><input type="checkbox" id="binding-enabled" ' + (binding.enabled !== false ? 'checked' : '') + '> Enabled</label>' : '') +
            '</div>' +
            '<div class="drawer-section">' +
            '<button class="btn btn-primary" id="btn-save-binding">' + (isEdit ? 'Update' : 'Create') + '</button>' +
            (isEdit ? '<button class="btn btn-secondary" id="btn-delete-binding" style="margin-left: 8px;">Delete</button>' : '') +
            '</div>';

        var body = window.openDrawer(title, html);

        body.querySelector('#btn-save-binding').addEventListener('click', function() {
            var chatId = body.querySelector('#binding-chat-id').value.trim();
            var botName = body.querySelector('#binding-bot-name').value.trim();

            if (!chatId) { window.showToast('Chat ID is required', 'warning'); return; }

            var endpoint = channel === 'telegram' ? '/api/telegram/bindings' : '/api/messenger/bindings';
            var payload = { chatId: chatId, botName: botName };

            if (isEdit) {
                payload.enabled = body.querySelector('#binding-enabled').checked;
                window.api.put(endpoint + '/' + binding.id, payload)
                    .then(function() {
                        window.showToast(channelLabel + ' binding updated', 'success');
                        window.closeDrawer();
                        loadAll();
                    })
                    .catch(function(err) { window.showToast('Failed: ' + err.message, 'error'); });
            } else {
                payload.enabled = true;
                window.api.post(endpoint, payload)
                    .then(function() {
                        window.showToast(channelLabel + ' binding created', 'success');
                        window.closeDrawer();
                        loadAll();
                    })
                    .catch(function(err) { window.showToast('Failed: ' + err.message, 'error'); });
            }
        });

        if (isEdit) {
            body.querySelector('#btn-delete-binding').addEventListener('click', function() {
                window.showConfirm('Delete Binding', 'Remove this ' + channelLabel + ' binding?')
                    .then(function(confirmed) {
                        if (!confirmed) return;
                        var endpoint = channel === 'telegram' ? '/api/telegram/bindings' : '/api/messenger/bindings';
                        window.api.del(endpoint + '/' + binding.id)
                            .then(function() {
                                window.showToast('Binding deleted', 'success');
                                window.closeDrawer();
                                loadAll();
                            })
                            .catch(function(err) { window.showToast('Failed: ' + err.message, 'error'); });
                    });
            });
        }
    }
}
