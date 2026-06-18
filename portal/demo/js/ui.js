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
        const originalLabel = button.textContent;
        const originalDisabled = button.disabled;
        button.disabled = true;
        button.dataset.sdBusy = '1';
        if (busyLabel) button.textContent = busyLabel;
        return function done() {
            button.disabled = originalDisabled;
            delete button.dataset.sdBusy;
            if (busyLabel) button.textContent = originalLabel;
        };
    }

    window.SD_UI = { qs, qsAll, toast, setButtonBusy };
})();
