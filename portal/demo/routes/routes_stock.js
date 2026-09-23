'use strict';

/**
 * Rutas — "Stock del día": what the company has per SKU when the day starts
 * and what is left as the sellers register sales on their visits.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.isAuthenticated()) return;
    const { qs, toast, setButtonBusy } = window.SD_UI;
    const T = window.SD_TRACK;

    qs('#stockDate').value = T.todayIso();
    qs('#stockViewDate').value = T.todayIso();

    /**
     * One product per line: "SKU, quantity[, name]". Commas or semicolons;
     * blank lines ignored. Errors name the line so the user fixes it.
     */
    function parseLines(text) {
        const items = [];
        text.split(/\r?\n/).forEach((raw, index) => {
            const line = raw.trim();
            if (!line) return;
            const parts = line.split(/[;,\t]/).map((part) => part.trim());
            const quantity = Number(parts[1]);
            if (!parts[0] || parts.length < 2 || isNaN(quantity) || quantity < 0) {
                throw new Error(`Línea ${index + 1}: se espera "SKU, cantidad[, nombre]".`);
            }
            items.push({ sku: parts[0], quantity, product_name: parts[2] || null });
        });
        if (!items.length) throw new Error('No hay productos para cargar.');
        return items;
    }

    qs('#stockLoadButton').addEventListener('click', async () => {
        const date = qs('#stockDate').value;
        if (!date) { note('#stockNote', 'Indica la fecha.', 'error'); return; }
        const done = setButtonBusy(qs('#stockLoadButton'), 'Cargando…');
        try {
            const items = parseLines(qs('#stockLines').value);
            const day = await T.stock.load({ date, items });
            note('#stockNote', `${day.skus_loaded} producto(s) cargados para ${date}.`, 'success');
            toast('Stock del día cargado.', 'success');
            qs('#stockViewDate').value = date;
            paintDay(day);
        } catch (error) {
            note('#stockNote', T.errorText(error, 'No se pudo cargar el stock.'), 'error');
        } finally {
            done();
        }
    });

    async function loadDay() {
        const date = qs('#stockViewDate').value || T.todayIso();
        note('#stockViewNote', 'Consultando…');
        try {
            paintDay(await T.stock.day(date));
            note('#stockViewNote', '');
        } catch (error) {
            note('#stockViewNote', T.errorText(error, 'No se pudo leer el stock.'), 'error');
        }
    }

    function paintDay(day) {
        const tbody = qs('#stockTable tbody');
        tbody.innerHTML = '';
        day.items.forEach((item) => {
            const row = document.createElement('tr');
            if (item.available_quantity <= 0) row.classList.add('is-out');
            row.innerHTML =
                `<td>${T.escapeHtml(item.sku)}</td>` +
                `<td>${T.escapeHtml(item.product_name || '—')}</td>` +
                `<td class="numeric">${T.formatQuantity(item.opening_quantity)}</td>` +
                `<td class="numeric">${T.formatQuantity(item.sold_quantity)}</td>` +
                `<td class="numeric"><strong>${T.formatQuantity(item.available_quantity)}</strong></td>`;
            tbody.appendChild(row);
        });
        const sold = day.items.reduce((sum, item) => sum + Number(item.sold_quantity), 0);
        qs('#stockSummary').innerHTML =
            metric('Productos', String(day.skus_loaded)) +
            metric('Unidades vendidas', T.formatQuantity(sold)) +
            metric('Agotados', String(day.skus_out_of_stock));
        qs('#stockSummary').hidden = false;
        if (!day.items.length) note('#stockViewNote', `No hay stock cargado para ${day.date}.`);
    }

    function metric(label, value) {
        return `<div class="metric"><p class="metric-label">${T.escapeHtml(label)}</p>` +
               `<p class="metric-value">${T.escapeHtml(value)}</p></div>`;
    }
    function note(selector, text, kind) { T.note(qs(selector), text, kind); }

    qs('#stockRefresh').addEventListener('click', loadDay);
    qs('#stockViewDate').addEventListener('change', loadDay);

    let loaded = false;
    T.onShow('stock', () => { if (!loaded) { loaded = true; loadDay(); } });
});
