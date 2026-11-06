'use strict';

/**
 * Anulaciones y devoluciones: what was undone, by month and by reason, while
 * the sales the other views read stay net (Rafael, 6-nov-2026). Totals count
 * what stands; a reverted cancellation or return stays listed and stops
 * counting.
 */
(function (A) {
    if (!window.SD_AUTH.isAuthenticated()) return;
    const { qs } = window.SD_UI;
    const M = window.SD_MONEY;

    const KIND_LABELS = { CANCELLATION: 'Anulación', RETURN: 'Devolución' };
    const KIND_COLORS = { CANCELLATION: '#c0392b', RETURN: A.BRAND[2] };
    const STATE_LABELS = { ACTIVE: 'Vigente', REVERTED: 'Revertida' };

    /** One stacked bar per month: cancellations and returns, in the chart currency. */
    function renderReversalsChart(months) {
        const labels = [...new Set(months.map((row) => row.month))].sort();
        A.makeChart('chartReversals', {
            type: 'bar',
            data: {
                labels: labels.map((month) => A.formatDateMonth(month)),
                datasets: Object.keys(KIND_LABELS).map((kind) => ({
                    label: KIND_LABELS[kind],
                    backgroundColor: KIND_COLORS[kind],
                    data: labels.map((month) => {
                        const row = months.find((item) => item.month === month &&
                                                          item.kind === kind);
                        return row ? A.chartAmount(row.amount) : 0;
                    })
                }))
            },
            options: {
                ...A.chartOptions('chartMoney'),
                plugins: { ...A.chartOptions('chartMoney').plugins,
                           legend: { position: 'bottom' } },
                scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true } }
            }
        });
    }

    function renderReversals(data, view) {
        const empty = qs('#reversalsEmpty');
        empty.hidden = (data.reversals || []).length > 0;
        empty.textContent = 'No hay anulaciones ni devoluciones en el período.';
        A.fillKpis('reversalsKpis', data.count ? [
            { label: 'Anulado y devuelto', value: data.amount, format: 'money3',
              hint: 'Lo que sigue vigente; cada mes al tipo de su cierre' },
            { label: 'Notas', value: data.count, format: 'int',
              hint: 'Anulaciones y devoluciones vigentes' },
            { label: 'Unidades', value: data.quantity, format: 'decimal',
              hint: 'Volvieron al inventario o no salieron' }
        ] : []);
        renderReversalsChart(data.months || []);
        A.fillTable('reversalsReasons', data.reasons || [], (row) =>
            `<td>${KIND_LABELS[row.kind] || row.kind}</td>` +
            `<td>${A.escapeHtml(row.reason || 'Sin motivo')}</td>` +
            `<td class="numeric">${A.formatInt(row.count)}</td>` +
            M.cells(row.amount, 2),
            { emptyText: 'Sin motivos en el período.' });
        A.fillTable('reversalsTable', data.reversals || [], (row) =>
            `<td>${A.formatDate(row.date)}</td>` +
            `<td>${KIND_LABELS[row.kind] || row.kind}</td>` +
            `<td>${A.escapeHtml(row.order_id)}</td>` +
            `<td>${A.escapeHtml(row.reversal_id)}</td>` +
            `<td>${A.escapeHtml(row.lines.map((line) => line.product_name).join(', '))}</td>` +
            `<td class="numeric">${A.formatDecimal(row.quantity, 2)}</td>` +
            `<td class="numeric">${A.formatDecimal(row.amount, 2)}</td>` +
            `<td>${STATE_LABELS[row.state] || row.state}</td>` +
            `<td>${A.escapeHtml(row.reason || '—')}</td>`,
            { emptyText: 'Sin anulaciones ni devoluciones.' });
        A.showAnalysisView(view || 'stepReversals');
    }

    Object.assign(A, { renderReversals, renderReversalsChart });
})(window.SD_ANALYSIS = window.SD_ANALYSIS || {});
