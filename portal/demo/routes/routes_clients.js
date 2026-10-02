'use strict';

/**
 * Rutas — "Clientes": the client master of the account, newest first.
 *
 * INGEST owns it and it is fed through three doors: the file, the ERP's API
 * and the seller who registers a new client standing at the door. The last one
 * is what the manager needs to see: a client nobody loaded, with coordinates a
 * phone read on the spot.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.isAuthenticated()) return;
    const { qs } = window.SD_UI;
    const T = window.SD_TRACK;

    const ROWS_PER_PAGE = 10;
    const SOURCE_LABELS = { FIELD: 'Alta en la calle', FILE: 'Archivo', API: 'Sistema (API)' };
    const state = { clients: [], shown: [], page: 0 };

    async function load() {
        T.note(qs('#clientsNote'), 'Consultando…');
        try {
            const data = await window.SD_API.get(
                `${window.SD_CONFIG.INGEST_URL}/v1/ingest/clients`);
            // Newest first: a client registered today is what the manager came for.
            state.clients = (data.clients || []).slice()
                .sort((left, right) => String(right.created_at).localeCompare(String(left.created_at)));
            paintSummary(data);
            applyFilter();
            T.note(qs('#clientsNote'), state.clients.length ? ''
                : 'Todavía no hay clientes. Se crean al cargar el archivo de ventas.');
        } catch (error) {
            T.note(qs('#clientsNote'), T.errorText(error, 'No se pudieron leer los clientes.'),
                   'error');
        }
    }

    function paintSummary(data) {
        const fromField = state.clients.filter((client) => client.source === 'FIELD').length;
        qs('#clientsSummary').innerHTML =
            metric('Clientes', String(data.total)) +
            metric('Con ubicación', String(data.with_coordinates)) +
            metric('Nuevos de la calle', String(fromField));
    }

    function metric(label, value) {
        return `<div class="metric"><p class="metric-label">${T.escapeHtml(label)}</p>` +
               `<p class="metric-value">${T.escapeHtml(value)}</p></div>`;
    }

    function applyFilter() {
        const source = qs('#clientsSource').value;
        state.shown = source
            ? state.clients.filter((client) => client.source === source)
            : state.clients;
        paintPage(0);
    }

    // Ten rows per page with invisible filler, like every table of the portal.
    function paintPage(page) {
        const rows = state.shown;
        const pages = Math.max(1, Math.ceil(rows.length / ROWS_PER_PAGE));
        state.page = Math.min(Math.max(page, 0), pages - 1);
        const slice = rows.slice(state.page * ROWS_PER_PAGE, (state.page + 1) * ROWS_PER_PAGE);

        const located = (client) => client.latitude != null && client.longitude != null
            && !(Number(client.latitude) === 0 && Number(client.longitude) === 0);
        const tbody = qs('#clientsTable tbody');
        tbody.innerHTML = slice.map((client) =>
            `<tr><td>${T.escapeHtml(client.name || client.id)}</td>` +
            `<td>${SOURCE_LABELS[client.source] || T.escapeHtml(client.source)}</td>` +
            `<td>${T.escapeHtml(client.seller || '—')}</td>` +
            `<td>${T.escapeHtml(client.zone || '—')}</td>` +
            `<td>${T.escapeHtml(client.address || '—')}</td>` +
            `<td>${located(client)
                ? `<a href="https://www.openstreetmap.org/?mlat=${client.latitude}` +
                  `&mlon=${client.longitude}#map=18/${client.latitude}/${client.longitude}" ` +
                  'target="_blank" rel="noopener">Ver en el mapa</a>'
                : 'Sin ubicación'}</td>` +
            `<td>${T.formatStamp(client.created_at)}</td></tr>`).join('');
        if (rows.length > ROWS_PER_PAGE) {
            tbody.innerHTML += '<tr class="row-filler"><td colspan="7">&nbsp;</td></tr>'
                .repeat(ROWS_PER_PAGE - slice.length);
        }
        qs('#clientsCount').textContent = rows.length === 1 ? '1 cliente' : `${rows.length} clientes`;
        qs('#clientsPage').textContent = `${state.page + 1} / ${pages}`;
        qs('#clientsPrev').disabled = state.page === 0;
        qs('#clientsNext').disabled = state.page >= pages - 1;
        qs('#clientsPager').hidden = rows.length <= ROWS_PER_PAGE;
    }

    qs('#clientsSource').addEventListener('change', applyFilter);
    qs('#clientsRefresh').addEventListener('click', load);
    qs('#clientsPrev').addEventListener('click', () => paintPage(state.page - 1));
    qs('#clientsNext').addEventListener('click', () => paintPage(state.page + 1));

    let loaded = false;
    T.onShow('clients', () => { if (!loaded) { loaded = true; load(); } });
});
