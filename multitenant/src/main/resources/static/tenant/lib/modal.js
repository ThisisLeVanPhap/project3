(function() {
    'use strict';

    function showConfirm(title, message) {
        return new Promise(function(resolve) {
            var overlay = document.createElement('div');
            overlay.className = 'modal-overlay';
            overlay.innerHTML = '<div class="modal"><div class="modal-header"><h3>' + title + '</h3></div><div class="modal-body"><p>' + message + '</p></div><div class="modal-footer"><button class="btn btn-secondary" id="modal-cancel">Cancel</button><button class="btn btn-primary" id="modal-confirm">Confirm</button></div></div>';
            document.body.appendChild(overlay);

            var cancel = overlay.querySelector('#modal-cancel');
            var confirm = overlay.querySelector('#modal-confirm');

            cancel.addEventListener('click', function() {
                document.body.removeChild(overlay);
                resolve(false);
            });

            confirm.addEventListener('click', function() {
                document.body.removeChild(overlay);
                resolve(true);
            });

            overlay.addEventListener('click', function(e) {
                if (e.target === overlay) {
                    document.body.removeChild(overlay);
                    resolve(false);
                }
            });

            document.addEventListener('keydown', function handler(e) {
                if (e.key === 'Escape') {
                    document.body.removeChild(overlay);
                    document.removeEventListener('keydown', handler);
                    resolve(false);
                }
            });
        });
    }

    window.showConfirm = showConfirm;
})();
