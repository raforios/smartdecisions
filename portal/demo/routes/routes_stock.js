'use strict';

/**
 * Rutas — "Stock del día": what the company has per SKU when the day starts
 * and what is left as the sellers register sales on their visits.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.isAuthenticated()) return;
    const { qs, toast, setButtonBusy } = window.SD_UI;
    const T = window.SD_TRACK;

    qs('#stockFileDate').value = T.todayIso();
    qs('#stockViewDate').value = T.todayIso();

    // The stock file attaches to the account's sales dataset (`ensureDataset`).
    const ROWS_PER_PAGE = 10;
    const state = { items: [], page: 0 };

    /**
     * The stock template goes in through INGEST —same file, same validator as
     * in Análisis Comercial— and the day is then opened from what INGEST
     * stored. Two steps on purpose: a file can hold several days, and the day
     * the trucks leave with is the one chosen here.
     */
    qs('#stockFileButton').addEventListener('click', async () => {
        const date = qs('#stockFileDate').value;
        const file = qs('#stockFile').files[0];
        const datasetId = await window.SD_API.ensureDataset();
        if (!date) { note('#stockFileNote', 'Indica la fecha.', 'error'); return; }
        if (!file) { note('#stockFileNote', 'Elige el archivo de stock.', 'error'); return; }
        if (!datasetId) {
            note('#stockFileNote', 'Primero carga el archivo de ventas en Análisis Comercial: ' +
                 'el stock se engancha a él.', 'error');
            return;
        }
        const done = setButtonBusy(qs('#stockFileButton'), 'Subiendo…');
        try {
            note('#stockFileNote', 'Subiendo el archivo… 0%');
            const fileKey = await window.SD_API.uploadToBucket(file, (ratio) => {
                note('#stockFileNote', `Subiendo el archivo… ${Math.round(ratio * 100)}%`);
            });
            note('#stockFileNote', 'Validando el archivo…');
            const ingested = await window.SD_API.post(
                `${window.SD_CONFIG.INGEST_URL}/v1/ingest/${encodeURIComponent(datasetId)}` +
                '/stock/from-s3',
                { file_key: fileKey, file_name: file.name }
            );
            const summary = ingested.summary || {};
            if (!summary.valid_rows) {
                note('#stockFileNote', 'El archivo no tiene filas válidas. Revisa que use la ' +
                     'plantilla de Stock.', 'error');
                return;
            }
            try {
                const day = await T.stock.fromIngest({ dataset_id: datasetId, date });
                note('#stockFileNote', `${day.skus_loaded} producto(s) cargados para ${date}.`,
                     'success');
                toast('Stock del día cargado.', 'success');
                qs('#stockViewDate').value = date;
                paintDay(day);
            } catch (error) {
                // The file went in; what is missing is that day. Say which days it has.
                const range = summary.snapshot_start === summary.snapshot_end
                    ? summary.snapshot_start
                    : `${summary.snapshot_start} al ${summary.snapshot_end}`;
                note('#stockFileNote', error.code === 'NO_STOCK_FOR_DAY'
                    ? `El archivo se cargó, pero no tiene stock para ${date}. Trae: ${range}.`
                    : T.errorText(error, 'No se pudo cargar el stock.'), 'error');
            }
        } catch (error) {
            note('#stockFileNote', T.errorText(error, 'No se pudo subir el archivo.'), 'error');
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
        state.items = day.items;
        paintPage(0);
        const sold = day.items.reduce((sum, item) => sum + Number(item.sold_quantity), 0);
        qs('#stockSummary').innerHTML =
            metric('Productos', String(day.skus_loaded)) +
            metric('Unidades vendidas', T.formatQuantity(sold)) +
            metric('Agotados', String(day.skus_out_of_stock));
        qs('#stockSummary').hidden = false;
        if (!day.items.length) note('#stockViewNote', `No hay stock cargado para ${day.date}.`);
    }

    // Ten rows per page, like every other table in the portal; a file brings
    // dozens of products and the table must not push the page down.
    function paintPage(page) {
        const items = state.items;
        const pages = Math.max(1, Math.ceil(items.length / ROWS_PER_PAGE));
        state.page = Math.min(Math.max(page, 0), pages - 1);
        const shown = items.slice(state.page * ROWS_PER_PAGE, (state.page + 1) * ROWS_PER_PAGE);

        const tbody = qs('#stockTable tbody');
        tbody.innerHTML = '';
        shown.forEach((item) => {
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
        if (items.length > ROWS_PER_PAGE) {
            tbody.innerHTML += '<tr class="row-filler"><td colspan="5">&nbsp;</td></tr>'
                .repeat(ROWS_PER_PAGE - shown.length);
        }
        qs('#stockCount').textContent = items.length === 1 ? '1 producto' : `${items.length} productos`;
        qs('#stockPage').textContent = `${state.page + 1} / ${pages}`;
        qs('#stockPrev').disabled = state.page === 0;
        qs('#stockNext').disabled = state.page >= pages - 1;
        qs('#stockPager').hidden = items.length <= ROWS_PER_PAGE;
    }

    qs('#stockPrev').addEventListener('click', () => paintPage(state.page - 1));
    qs('#stockNext').addEventListener('click', () => paintPage(state.page + 1));

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
