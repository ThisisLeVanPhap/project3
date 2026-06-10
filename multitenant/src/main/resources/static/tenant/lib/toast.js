(function() {
    'use strict';

    function showToast(message, type) {
        type = type || 'info';
        var container = document.getElementById('toast-container');
        if (!container) return;

        var el = document.createElement('div');
        el.className = 'toast ' + type;
        el.textContent = message;
        container.appendChild(el);

        setTimeout(function() {
            el.style.opacity = '0';
            el.style.transition = 'opacity 0.3s';
            setTimeout(function() {
                if (el.parentNode) container.removeChild(el);
            }, 300);
        }, 3000);
    }

    window.showToast = showToast;
})();
