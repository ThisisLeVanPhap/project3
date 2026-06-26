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
                window.api.get('/api/messenger/bindings').catch(function() { return []; }),
                window.api.get('/api/chatbots').catch(function() { return []; })
            ]);
            renderBindings(contentEl, results[0], results[1], results[2]);
        } catch (err) {
            contentEl.innerHTML = '<div class="placeholder-card"><p>Failed to load: ' + err.message + '</p></div>';
        }
    }

    function renderBindings(el, telegram, messenger, chatbots) {
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
            openBindingDrawer('telegram', null, chatbots);
        });
        el.querySelector('#btn-add-messenger').addEventListener('click', function() {
            openBindingDrawer('messenger', null, chatbots);
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
                { key: 'botUsername', label: 'Bot', sortable: true },
                { key: 'status', label: 'Status', sortable: true },
                { key: 'createdAt', label: 'Created', sortable: true, render: function(row) {
                    return row.createdAt ? new Date(row.createdAt).toLocaleDateString() : '-';
                }}
            ],
            data: data,
            onRowClick: function(row) {
                openBindingDrawer(channel, row, null);
            },
            emptyMessage: 'No bindings'
        });
    }

    function chatbotOptionsHtml(chatbots) {
        if (!chatbots || !chatbots.length) return '';
        return chatbots.map(function(b) {
            var label = (b.name || b.channel || 'Bot') + ' (' + (b.mode || b.channel || '-') + ')';
            return '<option value="' + b.id + '">' + label + '</option>';
        }).join('');
    }

    function openBindingDrawer(channel, binding, chatbots) {
        var isEdit = !!binding;
        var channelLabel = channel.charAt(0).toUpperCase() + channel.slice(1);
        var title = isEdit ? 'Edit ' + channelLabel + ' Binding' : 'New ' + channelLabel + ' Binding';

        if (channel === 'telegram') {
            var html = '' +
                '<div class="drawer-section">' +
                '<h4>Configuration</h4>' +
                '<label>Chatbot</label>' +
                (isEdit
                    ? '<input type="text" class="form-input" value="' + (binding.botUsername || binding.id || '') + '" disabled>'
                    : '<select class="form-input" id="binding-chatbot-select">' +
                      (chatbots && chatbots.length ? chatbotOptionsHtml(chatbots) : '<option value="">No chatbots available</option>') +
                      '</select>') +
                '<label style="margin-top: 12px;">Bot Token</label>' +
                '<input type="text" class="form-input" id="binding-bot-token" value="' + (binding ? (binding.botToken || '') : '') + '" placeholder="8476765941:AAHu8Zo_..." />' +
                '</div>' +
                '<div class="drawer-section">' +
                '<button class="btn btn-primary" id="btn-save-binding">' + (isEdit ? 'Update' : 'Create') + '</button>' +
                (isEdit ? '<button class="btn btn-secondary" id="btn-delete-binding" style="margin-left: 8px;">Delete</button>' : '') +
                '</div>';

            var body = window.openDrawer(title, html);

            body.querySelector('#btn-save-binding').addEventListener('click', function() {
                if (isEdit) return;
                var chatbotId = body.querySelector('#binding-chatbot-select')?.value;
                var botToken = body.querySelector('#binding-bot-token').value.trim();
                if (!chatbotId) { window.showToast('Select a chatbot', 'warning'); return; }
                if (!botToken) { window.showToast('Bot token is required', 'warning'); return; }

                window.api.post('/api/telegram/bindings', { chatbotId: chatbotId, botToken: botToken })
                    .then(function() {
                        window.showToast(channelLabel + ' binding created', 'success');
                        window.closeDrawer();
                        loadAll();
                    })
                    .catch(function(err) { window.showToast('Failed: ' + err.message, 'error'); });
            });

            if (isEdit) {
                body.querySelector('#btn-delete-binding').addEventListener('click', function() {
                    window.showConfirm('Delete Binding', 'Remove this ' + channelLabel + ' binding?')
                        .then(function(confirmed) {
                            if (!confirmed) return;
                            window.api.del('/api/telegram/bindings/' + binding.id)
                                .then(function() {
                                    window.showToast('Binding deleted', 'success');
                                    window.closeDrawer();
                                    loadAll();
                                })
                                .catch(function(err) { window.showToast('Failed: ' + err.message, 'error'); });
                        });
                });
            }
        } else {
            // Messenger: giữ nguyên form cũ nhưng thêm chatbot select
            var html = '' +
                '<div class="drawer-section">' +
                '<h4>Configuration</h4>' +
                '<label>Chatbot</label>' +
                (isEdit
                    ? '<input type="text" class="form-input" value="' + (binding.pageId || binding.id || '') + '" disabled>'
                    : '<select class="form-input" id="binding-chatbot-select">' +
                      (chatbots && chatbots.length ? chatbotOptionsHtml(chatbots) : '<option value="">No chatbots available</option>') +
                      '</select>') +
                '<label style="margin-top: 12px;">Page ID</label>' +
                '<input type="text" class="form-input" id="binding-page-id" value="' + (binding ? (binding.pageId || '') : '') + '" placeholder="Facebook Page ID" />' +
                '<label style="margin-top: 12px;">Page Access Token</label>' +
                '<input type="text" class="form-input" id="binding-page-token" value="' + (binding ? (binding.pageAccessToken || '') : '') + '" placeholder="EAAB..." />' +
                '</div>' +
                '<div class="drawer-section">' +
                '<button class="btn btn-primary" id="btn-save-binding">' + (isEdit ? 'Update' : 'Create') + '</button>' +
                (isEdit ? '<button class="btn btn-secondary" id="btn-delete-binding" style="margin-left: 8px;">Delete</button>' : '') +
                '</div>';

            var body = window.openDrawer(title, html);

            body.querySelector('#btn-save-binding').addEventListener('click', function() {
                if (isEdit) return;
                var chatbotId = body.querySelector('#binding-chatbot-select')?.value;
                var pageId = body.querySelector('#binding-page-id').value.trim();
                var pageToken = body.querySelector('#binding-page-token').value.trim();
                if (!chatbotId) { window.showToast('Select a chatbot', 'warning'); return; }
                if (!pageId || !pageToken) { window.showToast('Page ID and access token are required', 'warning'); return; }

                window.api.post('/api/messenger/bindings', { chatbotId: chatbotId, pageId: pageId, pageAccessToken: pageToken, enabled: true })
                    .then(function() {
                        window.showToast(channelLabel + ' binding created', 'success');
                        window.closeDrawer();
                        loadAll();
                    })
                    .catch(function(err) { window.showToast('Failed: ' + err.message, 'error'); });
            });

            if (isEdit) {
                body.querySelector('#btn-delete-binding').addEventListener('click', function() {
                    window.showConfirm('Delete Binding', 'Remove this ' + channelLabel + ' binding?')
                        .then(function(confirmed) {
                            if (!confirmed) return;
                            window.api.del('/api/messenger/bindings/' + binding.id)
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
}
