'use strict';

/**
 * Administración › Eventos y alertas — the last hours of the platform, from
 * EVENTS: answered and failed calls per hour, each service, the latest
 * failures and the latest audited changes. The reading lives in
 * js/platform_events.js, shared with the segment on Principal.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.isAuthenticated() || !window.SD_CONFIG.API_URL) return;
    const E = window.SD_EVENTS;
    const { qs, setButtonBusy } = window.SD_UI;
    const escape = (text) => String(text == null ? '' : text)
        .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
    const number = (value) => (value == null ? '—' : Number(value).toLocaleString('es-BO'));
    const count = (value, bad) => (value ? `<b class="${bad ? 'text-bad' : ''}">${number(value)}</b>` : '0');
    let chart = null;

    function paint(activity) {
        const totals = E.totals(activity);
        const errors = totals.clientErrors + totals.serverErrors;
        qs('#eventsSummary').textContent = `${number(totals.calls)} llamadas; ` +
            `${number(errors)} con error en ${number(totals.failing)} servicios.`;
        chart = E.chart(qs('#eventsChart'), activity, chart);
        // The services with errors first: what needs a look is on top.
        const services = activity.services.slice().sort((left, right) =>
            (right.client_errors + right.server_errors) - (left.client_errors + left.server_errors) ||
            right.total - left.total);
        qs('#eventsServices tbody').innerHTML = services.map((item) =>
            `<tr><td><b>${escape(item.microservice)}</b></td>` +
            `<td class="numeric">${number(item.total)}</td>` +
            `<td class="numeric">${number(item.ok)}</td>` +
            `<td class="numeric">${count(item.client_errors, true)}</td>` +
            `<td class="numeric">${count(item.server_errors, true)}</td>` +
            `<td class="numeric">${item.avg_response_ms == null ? '—' : `${number(item.avg_response_ms)} ms`}</td></tr>`)
            .join('');
        qs('#eventsErrors tbody').innerHTML = activity.latest_errors.map((call) =>
            `<tr><td>${E.when(call.timestamp)}</td><td>${escape(call.microservice)}</td>` +
            `<td><code>${escape(call.method || '')} ${escape(call.endpoint || '')}</code></td>` +
            `<td class="numeric"><span class="sd-status is-bad">${call.status_code}</span></td>` +
            `<td>${escape(call.user_id || '—')}</td>` +
            `<td class="numeric">${call.response_time_ms == null ? '—' : `${number(call.response_time_ms)} ms`}</td></tr>`)
            .join('') || '<tr class="empty-row"><td colspan="6">Sin errores en el período.</td></tr>';
        qs('#eventsChanges tbody').innerHTML = activity.latest_changes.map((change) =>
            `<tr><td>${E.when(change.timestamp)}</td><td>${escape(change.microservice)}</td>` +
            `<td>${escape(E.actionLabel(change.action))}</td>` +
            `<td>${escape(change.entity_name || '')} <code>${escape(change.entity_id || '')}</code></td>` +
            `<td>${escape(change.user_id || '—')}</td></tr>`)
            .join('') || '<tr class="empty-row"><td colspan="5">Sin cambios en el período.</td></tr>';
    }

    async function load(button) {
        const done = button ? setButtonBusy(button, 'Leyendo…') : () => {};
        try {
            paint(await E.load(Number(qs('#eventsHours').value)));
            qs('#eventsNote').textContent = '';
        } catch (error) {
            qs('#eventsNote').className = 'form-note error';
            qs('#eventsNote').textContent = 'No se pudieron leer los eventos.';
        } finally {
            done();
        }
    }

    qs('#eventsHours').addEventListener('change', () => load());
    qs('#eventsRefresh').addEventListener('click', (event) => load(event.currentTarget));
    load();
});
