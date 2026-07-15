/**
 * Landing modals: welcome popup on load + reusable image modal.
 * Plain (non-module) script, loaded via <script src> at the end of index.html.
 */
(function () {
    'use strict';

    var WELCOME_IMAGE = 'assets/popup.jpeg';
    var WELCOME_KEY = 'cumbre_welcome_seen';

    function buildOverlay(inner) {
        var overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.innerHTML =
            '<div class="modal-box" role="dialog" aria-modal="true">' +
            '<button class="modal-close" aria-label="Cerrar">&times;</button>' +
            inner +
            '</div>';
        return overlay;
    }

    function openOverlay(overlay) {
        document.body.appendChild(overlay);
        // Force reflow so the CSS transition runs.
        void overlay.offsetWidth;
        overlay.classList.add('is-open');
        document.body.style.overflow = 'hidden';

        function close() {
            overlay.classList.remove('is-open');
            document.body.style.overflow = '';
            document.removeEventListener('keydown', onKey);
            setTimeout(function () {
                if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
            }, 250);
        }
        function onKey(event) {
            if (event.key === 'Escape') close();
        }

        overlay.querySelector('.modal-close').addEventListener('click', close);
        overlay.addEventListener('click', function (event) {
            if (event.target === overlay) close();
        });
        document.addEventListener('keydown', onKey);
        return close;
    }

    function openImageModal(src, caption) {
        var inner = '<img class="modal-image" src="' + src + '" alt="' +
            (caption || '') + '">' +
            (caption ? '<p class="modal-caption">' + caption + '</p>' : '');
        openOverlay(buildOverlay(inner));
    }

    function showWelcome() {
        // Show once per browser session so it does not nag on every navigation.
        if (sessionStorage.getItem(WELCOME_KEY)) return;
        sessionStorage.setItem(WELCOME_KEY, '1');
        var inner = '<img class="modal-image" src="' + WELCOME_IMAGE +
            '" alt="Bienvenida a la Cumbre Nacional Minera">';
        var overlay = buildOverlay(inner);
        overlay.classList.add('modal-welcome');
        openOverlay(overlay);
    }

    function wireImageTriggers() {
        var triggers = document.querySelectorAll('[data-image-modal]');
        triggers.forEach(function (el) {
            function fire() {
                openImageModal(el.getAttribute('data-image-modal'),
                    el.getAttribute('data-image-caption'));
            }
            el.addEventListener('click', fire);
            el.addEventListener('keydown', function (event) {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    fire();
                }
            });
        });
    }

    function init() {
        wireImageTriggers();
        showWelcome();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
