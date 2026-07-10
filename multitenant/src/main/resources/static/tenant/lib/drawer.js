(function() {
    'use strict';

    var drawerEl = null;
    var overlayEl = null;

    function openDrawer(title, contentHtml) {
        closeDrawer();

        overlayEl = document.createElement('div');
        overlayEl.className = 'drawer-overlay';
        overlayEl.addEventListener('click', closeDrawer);
        document.body.appendChild(overlayEl);

        drawerEl = document.createElement('div');
        drawerEl.className = 'drawer';
        drawerEl.innerHTML = '<div class="drawer-header"><h3>' + title + '</h3><button class="btn btn-secondary" id="drawer-close">Close</button></div><div class="drawer-body">' + contentHtml + '</div>';
        document.body.appendChild(drawerEl);

        setTimeout(function() {
            drawerEl.classList.add('open');
        }, 10);

        var closeBtn = drawerEl.querySelector('#drawer-close');
        if (closeBtn) closeBtn.addEventListener('click', closeDrawer);

        document.addEventListener('keydown', handleEsc);

        return drawerEl.querySelector('.drawer-body');
    }

    function closeDrawer() {
        if (drawerEl) {
            drawerEl.classList.remove('open');
            setTimeout(function() {
                if (drawerEl && drawerEl.parentNode) drawerEl.parentNode.removeChild(drawerEl);
                drawerEl = null;
            }, 300);
        }
        if (overlayEl && overlayEl.parentNode) {
            overlayEl.parentNode.removeChild(overlayEl);
            overlayEl = null;
        }
        document.removeEventListener('keydown', handleEsc);
    }

    function handleEsc(e) {
        if (e.key === 'Escape') closeDrawer();
    }

    window.openDrawer = openDrawer;
    window.closeDrawer = closeDrawer;
})();
