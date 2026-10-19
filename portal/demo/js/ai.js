'use strict';

/**
 * Hook for the interpretation layer.
 *
 * Every view registers what it is currently showing, as data. When the AI
 * service exists, the button below hands it that payload and renders the
 * answer — the layer never has to scrape the DOM to find out what the user is
 * looking at, which is what makes this hook worth building before the service.
 *
 * The button only appears when SD_CONFIG.API_URL is configured, so nothing dead
 * ships to the demo in the meantime.
 */
(function () {

    const views = new Map();

    // The AI service answers with stable codes; the user reads these instead.
    const ERRORS = {
        EMPTY_PAYLOAD: 'Todavía no hay resultados en esta vista.',
        PAYLOAD_TOO_LARGE: 'Hay demasiados datos en pantalla para interpretarlos de una vez.',
        ROLE_NOT_CONFIGURED: 'La interpretación de esta pantalla todavía no está habilitada.',
        ROLE_NOT_FOUND: 'La interpretación de esta pantalla todavía no está habilitada.',
        MODEL_UNAVAILABLE: 'El servicio de interpretación no responde ahora. Intenta en unos minutos.',
        MODEL_REFUSED: 'No se pudo interpretar esta vista.',
        PARAMETER_MISSING: 'Falta configurar el servicio de interpretación.',
        PARAMETERS_SERVICE_NOT_CONFIGURED: 'Falta configurar el servicio de interpretación.',
        PARAMETERS_SERVICE_UNREACHABLE: 'El servicio de interpretación no responde ahora. Intenta en unos minutos.',
        PARAMETERS_SERVICE_REJECTED: 'El servicio de interpretación no responde ahora. Intenta en unos minutos.'
    };

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
     * Puts the "explain this" button on a view and renders the answer under it.
     *
     * The button goes wherever the section already keeps its controls; the
     * answer renders in its own panel below, because a paragraph inside a flex
     * header would fight the layout. Nothing is mounted when SD_CONFIG.API_URL
     * is missing — the portal works the same, only without explanations.
     *
     * @param {Element|string} host  Element (or its id) that holds the button.
     * @param {string} viewId        View whose payload is sent.
     * @param {Element} [panelHost]  Where the answer goes; defaults next to host.
     */
    function mountExplain(host, viewId, panelHost) {
        const holder = typeof host === 'string' ? document.getElementById(host) : host;
        if (!holder || !window.SD_CONFIG.API_URL) return;

        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'btn btn-ghost btn-small ai-ask';
        button.innerHTML = '<span aria-hidden="true">✨</span> ¿Qué significa esto?';

        // The answer goes immediately after the block that holds the button.
        // Appending it to the end of the section pushed it below the whole
        // chart or table, so the reader pressed a button and nothing seemed to
        // happen: what changed was off the bottom of the screen.
        const panel = document.createElement('div');
        panel.className = 'ai-answer';
        panel.hidden = true;
        const anchor = panelHost || holder;
        anchor.insertAdjacentElement('afterend', panel);

        button.addEventListener('click', async () => {
            const payload = payloadOf(viewId);
            if (!payload) {
                panel.hidden = false;
                panel.textContent = 'Todavía no hay resultados en esta vista.';
                return;
            }
            const done = window.SD_UI.setButtonBusy(button, 'Interpretando…');
            panel.hidden = false;
            panel.innerHTML = '<span class="ai-loading">Leyendo los números…</span>';
            // Bring it into view: the button may sit above the fold of a long
            // section, and an answer nobody sees is an answer that did not
            // arrive.
            panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            try {
                const answer = await window.SD_API.post(
                    `${window.SD_CONFIG.API_URL}/v1/ai/explain`,
                    { view: viewId, data: payload }
                );
                render(panel, answer);
            } catch (error) {
                panel.textContent = ERRORS[error && error.code]
                    || 'No se pudo obtener la interpretación.';
            } finally {
                done();
            }
        });

        holder.appendChild(button);
    }

    /**
     * Renders the interpretation.
     *
     * Only the answer. The response also carries the expert's full instructions
     * — how to read the view, what never to say — and that is the prompt, not
     * content: showing it put a wall of internal configuration under every
     * explanation. What stays is whether the answer was reused, which is
     * information for the reader and not for the machine.
     */
    function render(panel, answer) {
        panel.innerHTML = '';

        const body = document.createElement('p');
        body.className = 'ai-text';
        body.textContent = (answer && answer.text) || '';
        panel.appendChild(body);

        // Every answer says where it comes from (Anthropic's Usage Policy).
        const meta = document.createElement('p');
        meta.className = 'ai-meta';
        meta.textContent = 'Texto generado por IA; revísalo antes de decidir.' +
            (answer && answer.cached ? ' Respuesta guardada de una consulta anterior.' : '');
        panel.appendChild(meta);
    }

    window.SD_AI = { registerView, payloadOf, mountExplain, render };
})();
