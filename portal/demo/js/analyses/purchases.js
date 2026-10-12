'use strict';

/**
 * Compras: what the last purchase of each product cost against the previous
 * ones, and what the same purchase costs today. Each purchase reads at the
 * rate of its own day; next to it, today and the difference, which is what
 * says whether to adjust the price and the next order.
 */
(function (A) {
    if (!window.SD_AUTH.isAuthenticated()) return;
    const { qs } = window.SD_UI;
    const M = window.SD_MONEY;

    const UNAVAILABLE = {
        NO_PURCHASES: 'Todavía no cargaste compras. Súbelas arriba: fecha, proveedor, ' +
            'producto, cantidad, costo unitario y la moneda en que pagaste.'
    };
    const CURRENCY_LABELS = { BOB: 'Bs', USD: 'USD', USDT: 'USDT' };

    function percent(value) {
        return value == null ? '—' : `${A.formatDecimal(value, 1)}%`;
    }

    function renderPurchases(data, view) {
        const empty = qs('#purchasesEmpty');
        empty.hidden = data.available !== false;
        empty.textContent = UNAVAILABLE[data.reason_code] || '';
        A.fillKpis('purchasesKpis', data.available ? [
            { label: `Compras de ${A.formatDateMonth(data.month)}`, value: data.month_amount,
              format: 'money3', hint: 'Al tipo de cambio del cierre de ese mes' },
            { label: 'Compras registradas', value: data.purchases_count, format: 'int',
              hint: `${A.formatInt(data.suppliers)} proveedores` },
            { label: 'Último costo subió', value: data.cost_up, format: 'int',
              hint: 'Productos más caros que en la compra anterior' },
            { label: 'Último costo bajó', value: data.cost_down, format: 'int',
              hint: 'Productos más baratos que en la compra anterior' }
        ] : []);
        A.fillTable('purchasesTable', data.products || [], (row) =>
            `<td>${A.escapeHtml(row.product_name || row.product_id)}</td>` +
            `<td>${A.escapeHtml(row.supplier || '—')}</td>` +
            `<td>${A.formatDate(row.last_date)}</td>` +
            `<td>${CURRENCY_LABELS[row.currency] || row.currency}</td>` +
            M.cells(row.last_cost, 2) +
            `<td class="numeric">${row.previous_cost ? A.formatDecimal(row.previous_cost.bob, 2)
                : '—'}</td>` +
            `<td class="numeric ${A.deltaClass(-(row.change_vs_previous || 0))}">` +
            `${row.change_vs_previous == null ? '—' : A.formatDelta(row.change_vs_previous)}</td>` +
            M.cells(row.cost_today, 2) +
            M.cells(row.difference_today, 2, row.difference_today.bob > 0 ? 'delta-down' : '') +
            `<td class="numeric">${row.sale_price == null ? '—'
                : A.formatDecimal(row.sale_price, 2)}</td>` +
            `<td class="numeric">${percent(row.margin_at_last_cost)}</td>` +
            `<td class="numeric">${percent(row.margin_at_cost_today)}</td>`,
            { emptyText: 'Sin compras.' });
        A.showAnalysisView(view || 'stepPurchases');
    }

    Object.assign(A, { renderPurchases });
})(window.SD_ANALYSIS = window.SD_ANALYSIS || {});
