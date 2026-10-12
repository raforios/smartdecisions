'use strict';

/**
 * Efecto del tipo de cambio: real growth, replacement and purchasing power.
 */
(function (A) {
    if (!window.SD_AUTH.isAuthenticated()) return;
    const { qs, qsAll, toast, setButtonBusy } = window.SD_UI;

    function renderFx(data) {
        A.policyNotice('commercial', 'stepFx');

        const bs = (value) => (value == null || isNaN(value)) ? '—'
            : `Bs ${Number(value).toLocaleString('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        const usd = (value) => (value == null || isNaN(value)) ? '—'
            : `US$ ${Number(value).toLocaleString('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        const pct = (value) => (value == null || isNaN(value)) ? '—' : `${A.formatDecimal(value, 1)}%`;
        const fuente = data.source === 'USDT' ? 'USDT' : 'oficial';

        qs('#fxNote').textContent = data.rate_is_hypothetical
            ? `Simulación con un tipo de cambio de ${A.formatDecimal(data.rate_today, 2)}: no se guarda nada.`
            : `Tipo de cambio ${fuente} de hoy: ${A.formatDecimal(data.rate_today, 2)} Bs por dólar.`;

        const totals = data.totals;
        const power = data.purchasing_power || {};
        const box = qs('#fxKpis');
        box.innerHTML = '';
        [
            { label: 'Crecimiento en bolivianos', value: pct(data.growth_bob_pct),
              hint: 'Primer mes contra último' },
            { label: 'Crecimiento en dólares', value: pct(data.growth_usd_pct),
              hint: 'Si es menor que en Bs, parte del crecimiento es el tipo de cambio',
              variant: data.growth_usd_pct != null && data.growth_bob_pct != null
                  && data.growth_usd_pct < data.growth_bob_pct ? 'warning' : '' },
            { label: 'Margen al costo de compra', value: totals ? pct(totals.historical_margin_pct) : '—',
              hint: totals ? bs(totals.historical_margin) : 'El archivo no trae costo' },
            { label: 'Margen al costo de reposición', value: totals ? pct(totals.replacement_margin_pct) : '—',
              hint: totals ? `${bs(totals.replacement_margin)} reponiendo hoy` : '',
              variant: totals && totals.replacement_margin < totals.historical_margin ? 'warning' : '' },
            { label: 'Lo vendido, en dólares de cada día', value: usd(power.usd_at_own_day),
              hint: 'Cada venta al tipo de su día' },
            { label: 'Lo vendido, en dólares de hoy', value: usd(power.usd_at_today),
              hint: power.difference != null ? `${usd(power.difference)} de poder de compra` : '',
              variant: power.difference < 0 ? 'warning' : '' }
        ].forEach((card) => box.appendChild(A.metricCard(card)));
        A.arrangeMetrics(box);

        const monthly = data.monthly || [];
        A.makeChart('chartFx', {
            type: 'bar',
            data: {
                labels: monthly.map((row) => row.month),
                datasets: [
                    { type: 'bar', label: 'Venta Bs', data: monthly.map((row) => row.sales_bob),
                      backgroundColor: A.BRAND[0], yAxisID: 'bs' },
                    { type: 'line', label: 'Venta US$', data: monthly.map((row) => row.sales_usd),
                      borderColor: A.BRAND[3], backgroundColor: A.BRAND[3], tension: 0.3, yAxisID: 'usd' }
                ]
            },
            options: {
                responsive: true,
                plugins: { legend: { position: 'bottom' } },
                scales: {
                    bs: { position: 'left', beginAtZero: true, title: { display: true, text: 'Bs' } },
                    usd: { position: 'right', beginAtZero: true, grid: { drawOnChartArea: false },
                           title: { display: true, text: 'US$' } }
                }
            }
        });

        qs('#fxCategoryCard').hidden = !totals;
        A.fillTable('fxCategoryTable', data.by_category || [], (row) =>
            `<td>${A.escapeHtml(row.category)}</td>` +
            window.SD_MONEY.cells(row.revenue, 0) +
            `<td class="numeric">${A.formatDecimal(row.usd_cost_share * 100, 0)}%</td>` +
            window.SD_MONEY.cells(row.historical_margin, 0) +
            window.SD_MONEY.cells(row.replacement_margin, 0) +
            window.SD_MONEY.cells(row.margin_lost, 0, 'delta-down'));

        const uncovered = data.uncovered || [];
        qs('#fxUncoveredCard').hidden = !totals;
        qs('#fxUncoveredHint').textContent = data.uncovered_count
            ? `${A.formatInt(data.uncovered_count)} producto(s) se venden por debajo de lo que cuesta ` +
              `reponerlos hoy` + (data.uncovered_count > uncovered.length
                  ? `; se muestran los ${A.formatInt(uncovered.length)} con mayor diferencia.` : '.')
            : 'Todos los precios cubren lo que cuesta reponer hoy.';
        A.fillTable('fxUncoveredTable', uncovered, (row) =>
            `<td>${A.escapeHtml(row.product_name || row.product_id)}</td>` +
            `<td>${A.escapeHtml(row.category || '—')}</td>` +
            `<td class="numeric">${bs(row.last_price)}</td>` +
            `<td class="numeric">${bs(row.last_cost)}</td>` +
            `<td class="numeric">${bs(row.replacement_cost)}</td>` +
            `<td class="numeric">${bs(row.gap)}</td>`,
            { emptyText: 'Ningún producto por debajo de su costo de reposición.' });

        A.showAnalysisView('stepFx');
    }

    // A different dollar or a simulated rate is a different reading: fresh numbers.
    qs('#fxApply').addEventListener('click',
        (event) => A.openAnalysis('fx', event.currentTarget, true));

    Object.assign(A, {
        renderFx
    });
})(window.SD_ANALYSIS = window.SD_ANALYSIS || {});
