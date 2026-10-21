'use strict';

/**
 * Administración › Salud — the thirteen services and their tables, in green
 * or red. The checking lives in js/platform_health.js, shared with the card
 * on Principal.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.isAuthenticated() || !window.SD_CONFIG.API_URL) return;
    const { qs, setButtonBusy } = window.SD_UI;
    const escape = (text) => String(text == null ? '' : text)
        .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
    const number = (value) => (value == null ? '—' : Number(value).toLocaleString('es-BO'));

    const badge = (good, text) => `<span class="sd-status ${good ? 'is-on' : 'is-bad'}">${text}</span>`;

    function size(bytes) {
        if (bytes == null) return '—';
        const units = ['B', 'KB', 'MB', 'GB'];
        let value = bytes;
        let unit = 0;
        while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit += 1; }
        return `${value.toLocaleString('es-BO', { maximumFractionDigits: unit ? 1 : 0 })} ${units[unit]}`;
    }

    function tablesCell(item) {
        if (item.noTables) return 'No usa tablas';
        if (item.tablesError === 'NOT_DEPLOYED') return 'Falta desplegar la ruta';
        if (!item.tables) return badge(false, 'No se pudo leer');
        const active = item.tables.tables.filter((table) => table.status === 'ACTIVE').length;
        return badge(item.tables.healthy, `${active} de ${item.tables.tables.length} activas`);
    }

    async function load(button) {
        const done = button ? setButtonBusy(button, 'Revisando…') : () => {};
        try {
            const results = await window.SD_HEALTH.check();
            const totals = window.SD_HEALTH.summarize(results);
            qs('#healthSummary').textContent =
                `${totals.up} de ${totals.services} servicios responden. ` +
                `${window.SD_HEALTH.tablesLine(totals)}` +
                ` Revisado a las ${new Date().toLocaleTimeString('es-BO', { hour: '2-digit', minute: '2-digit' })}`;
            qs('#servicesTable tbody').innerHTML = results.map((item) =>
                `<tr><td><b>${item.label}</b>${item.base ? ' <span class="legend-hint">base</span>' : ''}</td>` +
                `<td>${badge(item.up, item.up ? 'Responde' : 'No responde')}</td>` +
                `<td class="numeric">${item.ms == null ? '—' : `${number(item.ms)} ms`}</td>` +
                `<td>${tablesCell(item)}</td></tr>`).join('');
            // Problems first: what needs a look is on the first page.
            const rows = results.filter((item) => item.tables).flatMap((item) =>
                item.tables.tables.map((table) => ({ service: item.label, ...table })))
                .sort((left, right) => (left.status === 'ACTIVE') - (right.status === 'ACTIVE'));
            qs('#tablesTable tbody').innerHTML = rows.map((table) =>
                `<tr><td>${table.service}</td><td><code>${escape(table.name)}</code></td>` +
                `<td>${badge(table.status === 'ACTIVE', escape(window.SD_HEALTH.stateLabel(table.status)))}</td>` +
                `<td class="numeric">${number(table.item_count)}</td>` +
                `<td class="numeric">${size(table.size_bytes)}</td></tr>`).join('');
            qs('#healthNote').textContent = rows.length ? '' : 'Ningún servicio informó sus tablas todavía.';
        } finally {
            done();
        }
    }

    qs('#healthRefresh').addEventListener('click', (event) => load(event.currentTarget));
    load();
});
