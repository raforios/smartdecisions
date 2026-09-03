'use strict';

/**
 * Session countdown, shared by every module page.
 *
 * The session used to die silently and bounce the user to the login screen
 * mid-analysis. Showing the remaining time makes that predictable. This lives
 * here and not inside a module page so both Análisis Comercial and Rutas show
 * exactly the same chip: one implementation, one behaviour.
 */
(function sessionModule() {
    const WARNING_MINUTES = 10;
    const REFRESH_MS = 60000;

    /**
     * Renders the remaining session time into a chip element.
     */
    function render(chip, state) {
        const expiry = window.SD_AUTH.getSessionExpiry();
        if (!expiry) {
            chip.hidden = true;
            return;
        }
        const minutes = Math.floor((expiry.getTime() - Date.now()) / 60000);
        chip.hidden = false;
        chip.classList.toggle('warning', minutes <= WARNING_MINUTES);
        if (minutes <= 0) {
            chip.textContent = '⏱ Sesión expirada — vuelve a entrar';
            return;
        }
        chip.textContent = minutes >= 60
            ? `⏱ Sesión: ${Math.floor(minutes / 60)} h ${minutes % 60} min`
            : `⏱ Sesión: ${minutes} min`;
        if (minutes <= WARNING_MINUTES && !state.warned) {
            state.warned = true;
            if (window.SD_UI && window.SD_UI.toast) {
                window.SD_UI.toast(
                    `Tu sesión expira en ${minutes} min. ${state.keepsWork}`, 'info', 9000
                );
            }
        }
    }

    /**
     * Starts the countdown on the chip with the given id.
     *
     * @param {string} chipId - Element id of the chip.
     * @param {string} keepsWork - Sentence explaining what survives the expiry.
     */
    function mountChip(chipId, keepsWork) {
        const chip = document.getElementById(chipId);
        if (!chip) return;
        const state = { warned: false, keepsWork: keepsWork || '' };
        render(chip, state);
        setInterval(() => render(chip, state), REFRESH_MS);
    }

    window.SD_SESSION = { mountChip };
})();
