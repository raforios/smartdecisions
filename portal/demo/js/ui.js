'use strict';

/**
 * UI helpers shared across module pages: toast notifications, button-busy
 * state and a small `qs/qsAll` shortcut so module code stays terse.
 */
(function () {

    function qs(selector, root) {
        return (root || document).querySelector(selector);
    }

    function qsAll(selector, root) {
        return Array.from((root || document).querySelectorAll(selector));
    }

    function _ensureToastContainer() {
        let container = document.getElementById('sd-toast-container');
        if (container) return container;
        container = document.createElement('div');
        container.id = 'sd-toast-container';
        container.className = 'sd-toast-container';
        document.body.appendChild(container);
        return container;
    }

    /**
     * Shows an ephemeral notification.
     * variant ∈ {'info', 'success', 'error'}.
     */
    function toast(message, variant = 'info', timeoutMs = 4500) {
        const container = _ensureToastContainer();
        const node = document.createElement('div');
        node.className = `sd-toast sd-toast-${variant}`;
        node.textContent = message;
        container.appendChild(node);
        setTimeout(() => {
            node.classList.add('sd-toast-leaving');
            setTimeout(() => node.remove(), 250);
        }, timeoutMs);
    }

    /**
     * Toggles a busy state on a <button>: disables it and shows the loading
     * label until `done()` is called. Returns the done() callback.
     */
    function setButtonBusy(button, busyLabel) {
        // Markup, not text: an analysis card is a button with an icon, a title
        // and a description inside, and restoring textContent flattened it
        // into one plain line after the first click.
        const originalMarkup = button.innerHTML;
        const originalDisabled = button.disabled;
        button.disabled = true;
        button.dataset.sdBusy = '1';
        if (busyLabel) button.textContent = busyLabel;
        return function done() {
            button.disabled = originalDisabled;
            delete button.dataset.sdBusy;
            if (busyLabel) button.innerHTML = originalMarkup;
        };
    }

    /**
     * The eye beside a password field: shows or hides what was typed, and the
     * button says which way it goes. Used by the login and by Mi cuenta.
     */
    function revealToggle(input, button) {
        const paint = () => {
            const shown = input.type === 'text';
            button.innerHTML = window.SD_ICONS.svg(shown ? 'eyeOff' : 'eye');
            button.setAttribute('aria-pressed', String(shown));
            button.setAttribute('aria-label', shown ? 'Ocultar la contraseña' : 'Mostrar la contraseña');
        };
        button.addEventListener('click', () => {
            input.type = input.type === 'password' ? 'text' : 'password';
            paint();
        });
        paint();
        return () => { input.type = 'password'; paint(); };
    }

    window.SD_UI = { qs, qsAll, toast, setButtonBusy, revealToggle };
})();
