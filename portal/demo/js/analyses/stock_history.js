'use strict';

/**
 * Evolución del inventario: every stored stock photo, at cost and at sale
 * price. Each photo reads in the dollars of its own day —the past is not
 * updated— and next to it the same bolivianos at today's rate. On the latest
 * photo that comparison is the price check.
 */
(function (A) {
    if (!window.SD_AUTH.isAuthenticated()) return;
    const { qs } = window.SD_UI;
    const M = window.SD_MONEY;

    const UNAVAILABLE = {
        NO_SNAPSHOT: 'Todavía no cargaste ninguna foto de stock. Súbela arriba, con su fecha.'
    };

    function renderPriceCheck(last) {
        const box = qs('#stockPriceCheck');
        const then = last && last.value_at_price;
        const now = last && last.value_at_price_today;
        if (!then || !now) {
            box.hidden = true;
            return;
        }
        const lost = M.minus(now, then);
        box.hidden = false;
        box.innerHTML =
            `<p>Tu lista de precios del ${A.formatDate(last.date)} valía ` +
            `<strong>${M.inline(then)}</strong> ese día; hoy esos mismos bolivianos valen ` +
            `<strong>${M.inline(now)}</strong>.</p>` +
            `<p>Diferencia: USD ${A.formatDecimal(lost.usd, 0)} · ` +
            `USDT ${A.formatDecimal(lost.usdt, 0)}. Si es negativa, tus precios perdieron ` +
            'valor en dólares y conviene revisar el ajuste.</p>';
    }

    function renderStockHistoryChart(photos) {
        A.makeChart('chartStockHistory', {
            type: 'line',
            data: {
                labels: photos.map((photo) => A.formatDate(photo.date)),
                datasets: [
                    { label: 'A precio de venta',
                      data: photos.map((photo) => A.chartAmount(photo.value_at_price)),
                      borderColor: A.BRAND[0], tension: 0.25 },
                    { label: 'A costo',
                      data: photos.map((photo) => A.chartAmount(photo.value_at_cost)),
                      borderColor: A.BRAND[2], tension: 0.25 }
                ]
            },
            options: (() => {
                // Two lines, so the legend says which is which.
                const options = A.chartOptions('chartMoney');
                options.plugins.legend.display = true;
                return options;
            })()
        });
    }

    function renderStockHistory(data, view) {
        const empty = qs('#stockHistoryEmpty');
        const photos = data.photos || [];
        empty.hidden = data.available !== false;
        empty.textContent = UNAVAILABLE[data.reason_code] || '';
        renderStockHistoryChart(photos);
        A.fillTable('stockHistoryTable', photos.slice().reverse(), (photo) =>
            `<td>${A.formatDate(photo.date)}</td>` +
            `<td class="numeric">${A.formatInt(photo.products)}</td>` +
            `<td class="numeric">${A.formatInt(photo.units_on_hand)}</td>` +
            `<td class="numeric">${A.formatInt(photo.out_of_stock)}</td>` +
            M.cells(photo.value_at_cost, 0) + M.cells(photo.value_at_price, 0) +
            M.cells(photo.value_at_price_today, 0),
            { emptyText: 'Sin fotos de stock.' });
        renderPriceCheck(photos[photos.length - 1]);
        A.showAnalysisView(view || 'stepStockHistory');
    }

    Object.assign(A, { renderStockHistory, renderStockHistoryChart });
})(window.SD_ANALYSIS = window.SD_ANALYSIS || {});
