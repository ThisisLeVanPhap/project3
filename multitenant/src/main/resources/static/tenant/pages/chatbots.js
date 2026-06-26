export async function render(container, params) {
    container.innerHTML = '' +
        '<div class="page">' +
        '<h1>Chatbots</h1>' +
        '<p class="subtitle">Configure chatbots per channel</p>' +
        '<div class="toolbar">' +
        '<button class="btn btn-primary" id="btn-create-bot">+ New Chatbot</button>' +
        '</div>' +
        '<div id="bots-content"></div>' +
        '</div>';

    var contentEl = container.querySelector('#bots-content');

    loadBots();

    container.querySelector('#btn-create-bot').addEventListener('click', function() {
        openBotDrawer(null);
    });

    async function loadBots() {
        contentEl.innerHTML = '<div class="skeleton-container">' +
            '<div class="skeleton skeleton-title"></div>' +
            '<div class="skeleton skeleton-card"></div>' +
            '<div class="skeleton skeleton-card"></div>' +
            '</div>';
        try {
            var bots = await window.api.get('/api/chatbots');
            renderTable(contentEl, bots);
        } catch (err) {
            contentEl.innerHTML = '<div class="placeholder-card"><p>Failed to load: ' + err.message + '</p></div>';
        }
    }

    function renderTable(el, data) {
        if (!data || !data.length) {
            el.innerHTML = '<div class="empty-state">' +
                '<div class="icon">🤖</div>' +
                '<div class="title">No chatbots configured</div>' +
                '<div class="description">Create a chatbot to start engaging with customers on Telegram or Messenger.</div>' +
                '</div>';
            return;
        }

        window.createTable(el, {
            columns: [
                { key: 'name', label: 'Name', sortable: true },
                { key: 'provider', label: 'Provider', sortable: true, render: function(row) {
                    return '<span class="badge badge-provider">' + (row.provider || '-') + '</span>';
                }},
                { key: 'modelId', label: 'Model', sortable: true },
                { key: 'enabled', label: 'Enabled', sortable: true, render: function(row) {
                    return row.enabled ? '<span class="badge badge-status-active">ON</span>' : '<span class="badge badge-status-inactive">OFF</span>';
                }},
                { key: 'createdAt', label: 'Created', sortable: true, render: function(row) {
                    return row.createdAt ? new Date(row.createdAt).toLocaleDateString() : '-';
                }}
            ],
            data: data,
            onRowClick: function(row) {
                openBotDrawer(row);
            },
            emptyMessage: 'No chatbots found'
        });
    }

    function openBotDrawer(bot) {
        var isEdit = !!bot;
        var title = isEdit ? 'Edit Chatbot' : 'New Chatbot';

        var html = '' +
            '<div class="drawer-section">' +
            '<h4>Configuration</h4>' +
            '<label>Name</label>' +
            '<input type="text" class="form-input" id="bot-name" value="' + (bot ? bot.name : '') + '" placeholder="e.g. Sales Bot">' +
            '<label style="margin-top: 12px;">Provider</label>' +
            '<select class="form-input" id="bot-provider">' +
            '<option value="claude"' + (!bot || bot.provider === 'claude' ? ' selected' : '') + '>Claude API</option>' +
            '<option value="local"' + (bot && bot.provider === 'local' ? ' selected' : '') + '>Local base model fallback</option>' +
            '</select>' +
            '<label style="margin-top: 12px;">Model ID</label>' +
            '<input type="text" class="form-input" id="bot-model" value="' + (bot ? (bot.baseModel || '') : '') + '" placeholder="Optional local base model">' +
            '<label style="margin-top: 12px;">System Prompt</label>' +
            '<textarea class="form-input" id="bot-prompt" rows="4" style="min-height: 100px;">' + (bot ? (bot.systemPrompt || '') : '') + '</textarea>' +
            (isEdit ? '<label style="margin-top: 12px;"><input type="checkbox" id="bot-enabled" ' + (bot.enabled ? 'checked' : '') + '> Enabled</label>' : '') +
            '</div>' +
            '<div class="drawer-section">' +
            '<button class="btn btn-primary" id="btn-save-bot">' + (isEdit ? 'Update' : 'Create') + '</button>' +
            (isEdit ? '<button class="btn btn-secondary" id="btn-delete-bot" style="margin-left: 8px;">Delete</button>' : '') +
            '</div>';

        var body = window.openDrawer(title, html);

        body.querySelector('#btn-save-bot').addEventListener('click', function() {
            var name = body.querySelector('#bot-name').value.trim();
            var provider = body.querySelector('#bot-provider').value;
            var modelId = body.querySelector('#bot-model').value.trim();
            var systemPrompt = body.querySelector('#bot-prompt').value;

            if (!name) { window.showToast('Name is required', 'warning'); return; }
            if (provider === 'local' && !modelId) { window.showToast('Local provider requires a base model', 'warning'); return; }

            var payload = {
                name: name,
                channel: 'web',
                provider: provider,
                personaJson: '{}',
                responseStyle: 'natural',
                baseModel: modelId,
                systemPrompt: systemPrompt
            };
            if (isEdit) {
                payload.enabled = body.querySelector('#bot-enabled').checked;
                window.api.put('/api/chatbots/' + bot.id, payload)
                    .then(function() {
                        window.showToast('Chatbot updated', 'success');
                        window.closeDrawer();
                        loadBots();
                    })
                    .catch(function(err) { window.showToast('Failed: ' + err.message, 'error'); });
            } else {
                payload.enabled = true;
                window.api.post('/api/chatbots', payload)
                    .then(function() {
                        window.showToast('Chatbot created', 'success');
                        window.closeDrawer();
                        loadBots();
                    })
                    .catch(function(err) { window.showToast('Failed: ' + err.message, 'error'); });
            }
        });

        if (isEdit) {
            body.querySelector('#btn-delete-bot').addEventListener('click', function() {
                window.showConfirm('Delete Chatbot', 'Are you sure you want to delete "' + bot.name + '"?')
                    .then(function(confirmed) {
                        if (!confirmed) return;
                        window.api.del('/api/chatbots/' + bot.id)
                            .then(function() {
                                window.showToast('Chatbot deleted', 'success');
                                window.closeDrawer();
                                loadBots();
                            })
                            .catch(function(err) { window.showToast('Failed: ' + err.message, 'error'); });
                    });
            });
        }
    }
}
