'use strict';

/**
 * Hook for the interpretation layer.
 *
 * Every view registers what it is currently showing, as data. When the AI
 * service exists, the button below hands it that payload and renders the
 * answer — the layer never has to scrape the DOM to find out what the user is
 * looking at, which is what makes this hook worth building before the service.
 *
 * The button only appears when SD_CONFIG.AI_URL is configured, so nothing dead
 * ships to the demo in the meantime.
 */
(function () {

    const views = new Map();

    /**
     * Registers a view and how to read its current data.
     *
     * @param {string} viewId Stable identifier of the view.
     * @param {Function} collect Returns the payload the view is showing.
     */
    function registerView(viewId, collect) {
        views.set(viewId, collect);
    }

    /**
     * Returns what a view is showing right now, or null if it is not registered.
     */
    function payloadOf(viewId) {
        const collect = views.get(viewId);
        return collect ? collect() : null;
    }

    /**
     * Mounts the "explain this" button into a container, if the layer is live.
     *
     * @param {string} containerId Element that hosts the button.
     * @param {string} viewId View whose payload the button sends.
     */
    function mountExplain(containerId, viewId) {
        const host = document.getElementById(containerId);
        if (!host || !window.SD_CONFIG.AI_URL) return;

        const button = document.createElement('button');
        button.className = 'btn btn-ghost btn-small';
        button.textContent = '¿Qué significa esto?';
        button.addEventListener('click', async () => {
            const payload = payloadOf(viewId);
            if (!payload) return;
            const done = window.SD_UI.setButtonBusy(button, 'Interpretando…');
            try {
                const answer = await window.SD_API.post(
                    `${window.SD_CONFIG.AI_URL}/v1/ai/explain`,
                    { view: viewId, data: payload }
                );
                window.SD_AI.render(host, answer);
            } catch (error) {
                window.SD_UI.toast(error.message, 'error');
            } finally {
                done();
            }
        });
        host.appendChild(button);
    }

    /**
     * Renders the interpretation next to the view that asked for it.
     */
    function render(host, answer) {
        let box = host.querySelector('.ai-answer');
        if (!box) {
            box = document.createElement('div');
            box.className = 'ai-answer';
            host.appendChild(box);
        }
        box.textContent = (answer && answer.text) || '';
    }

    window.SD_AI = { registerView, payloadOf, mountExplain, render };
})();
