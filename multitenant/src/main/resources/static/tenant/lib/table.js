(function() {
    'use strict';

    function createTable(container, options) {
        var columns = options.columns || [];
        var data = options.data || [];
        var onRowClick = options.onRowClick;
        var emptyMessage = options.emptyMessage || 'No data';

        var sortKey = null;
        var sortDir = 'asc';
        var filterText = '';
        var page = 0;
        var pageSize = 20;

        function render() {
            var filtered = data.filter(function(row) {
                if (!filterText) return true;
                return columns.some(function(col) {
                    var val = row[col.key];
                    return val && String(val).toLowerCase().indexOf(filterText.toLowerCase()) !== -1;
                });
            });

            if (sortKey) {
                filtered.sort(function(a, b) {
                    var va = a[sortKey], vb = b[sortKey];
                    if (va < vb) return sortDir === 'asc' ? -1 : 1;
                    if (va > vb) return sortDir === 'asc' ? 1 : -1;
                    return 0;
                });
            }

            var totalPages = Math.ceil(filtered.length / pageSize);
            var paged = filtered.slice(page * pageSize, (page + 1) * pageSize);

            var html = '<div class="table-controls"><input type="text" class="table-filter" placeholder="Filter..." value="' + filterText + '"></div>';

            if (paged.length === 0) {
                html += '<div class="empty-state"><div class="icon">📭</div><div class="title">No data found</div><div class="description">' + emptyMessage + '</div></div>';
            } else {
                html += '<table class="table"><thead><tr>';
                columns.forEach(function(col) {
                    var arrow = sortKey === col.key ? (sortDir === 'asc' ? ' ↑' : ' ↓') : '';
                    html += '<th data-key="' + col.key + '">' + col.label + arrow + '</th>';
                });
                html += '</tr></thead><tbody>';
                paged.forEach(function(row) {
                    html += '<tr>';
                    columns.forEach(function(col) {
                        var val = col.render ? col.render(row) : (row[col.key] || '');
                        html += '<td>' + val + '</td>';
                    });
                    html += '</tr>';
                });
                html += '</tbody></table>';

                if (totalPages > 1) {
                    html += '<div class="pagination">';
                    for (var i = 0; i < totalPages; i++) {
                        html += '<button class="btn btn-page ' + (i === page ? 'active' : '') + '" data-page="' + i + '">' + (i + 1) + '</button>';
                    }
                    html += '</div>';
                }
            }

            container.innerHTML = html;

            var filterInput = container.querySelector('.table-filter');
            if (filterInput) {
                filterInput.addEventListener('input', function(e) {
                    filterText = e.target.value;
                    page = 0;
                    render();
                });
            }

            container.querySelectorAll('th[data-key]').forEach(function(th) {
                th.addEventListener('click', function() {
                    var key = th.getAttribute('data-key');
                    if (sortKey === key) {
                        sortDir = sortDir === 'asc' ? 'desc' : 'asc';
                    } else {
                        sortKey = key;
                        sortDir = 'asc';
                    }
                    render();
                });
            });

            container.querySelectorAll('.btn-page').forEach(function(btn) {
                btn.addEventListener('click', function() {
                    page = parseInt(btn.getAttribute('data-page'));
                    render();
                });
            });

            if (onRowClick) {
                container.querySelectorAll('tbody tr').forEach(function(tr, idx) {
                    tr.addEventListener('click', function() {
                        onRowClick(paged[idx]);
                    });
                });
            }
        }

        render();

        return {
            setData: function(newData) {
                data = newData;
                page = 0;
                render();
            }
        };
    }

    window.createTable = createTable;
})();
