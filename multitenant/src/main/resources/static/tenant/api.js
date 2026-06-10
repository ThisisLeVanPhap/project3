(function() {
    'use strict';

    var api = {
        get: function(url) {
            return this._request(url, 'GET');
        },
        post: function(url, body) {
            return this._request(url, 'POST', body);
        },
        put: function(url, body) {
            return this._request(url, 'PUT', body);
        },
        del: function(url, body) {
            return this._request(url, 'DELETE', body);
        },
        _request: function(url, method, body) {
            var opts = {
                method: method,
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' }
            };
            if (body) opts.body = JSON.stringify(body);

            return fetch(url, opts).then(function(res) {
                if (res.status === 401) {
                    window.location.href = '/login';
                    return Promise.reject(new Error('Unauthorized'));
                }
                if (res.status === 403) {
                    if (window.showToast) window.showToast('Not authorized', 'error');
                    return Promise.reject(new Error('Forbidden'));
                }
                if (!res.ok) {
                    return res.text().then(function(text) {
                        var msg = text;
                        try {
                            var json = JSON.parse(text);
                            msg = json.message || json.error || text;
                        } catch(e) {}
                        return Promise.reject(new Error(msg || res.statusText));
                    });
                }
                var contentType = res.headers.get('content-type');
                if (contentType && contentType.indexOf('application/json') !== -1) {
                    return res.json();
                }
                return res.text();
            });
        }
    };

    // Global error handler for auth failures
    function wrapWithAuthHandler(methodName) {
        var original = api[methodName];
        api[methodName] = function(url, data) {
            return original.call(api, url, data).catch(function(err) {
                if (err.status === 401 || (err.message && err.message.indexOf('401') !== -1)) {
                    if (window.showToast) window.showToast('Session expired. Please login again.', 'error');
                    setTimeout(function() { window.location.href = '/login'; }, 2000);
                }
                throw err;
            });
        };
    }
    wrapWithAuthHandler('get');
    wrapWithAuthHandler('post');
    wrapWithAuthHandler('put');
    wrapWithAuthHandler('del');

    window.api = api;
})();
