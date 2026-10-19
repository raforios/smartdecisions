'use strict';

/** Balance General at the close of the chosen period, and its ratios. */
document.addEventListener('DOMContentLoaded', async () => {
    if (!window.SD_AUTH.isAuthenticated()) return;

    const F = window.SD_FINANCE;
    const { qs, toast } = window.SD_UI;

    const LINES = [
        ['assets', 'Activo', true],
        ['current_assets', 'Activo corriente'],
        ['cash', 'Efectivo (caja, bancos y billeteras)'],
        ['liabilities', 'Pasivo', true],
        ['current_liabilities', 'Pasivo corriente'],
        ['equity', 'Patrimonio', true],
        ['difference', 'Diferencia (Activo − Pasivo − Patrimonio)']
    ];
    const RATIOS = [
        ['liquidity', 'Liquidez', 'Activo corriente / pasivo corriente: más de 1, alcanza para lo que vence pronto.'],
        ['debt_ratio', 'Endeudamiento', 'Pasivo / activo: qué parte de lo que tienes es deuda.'],
        ['solvency', 'Solvencia', 'Activo / pasivo: cuántas veces cubre lo que tienes a lo que debes.'],
        ['coverage_months', 'Meses de cobertura', 'Efectivo frente a lo que sale en un mes, en promedio.']
    ];

    // What the AI reads: the chosen period and the report's notices, as the
    // backend returned them.
    let shown = null;

    function render(period, data) {
        shown = { period, notices: data.notices };
        const balance = period.balance;
        qs('#balanceTable tbody').innerHTML = LINES
            .map(([key, label, total]) => F.moneyRow(label, balance[key], period.exchange, total))
            .join('');
        F.arrange(qs('#indicators'), RATIOS.map(([key, label, hint]) => {
            const value = period.indicators[key];
            const shown = value == null ? '—' : value.toLocaleString('es-BO',
                { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            const node = document.createElement('div');
            node.className = 'metric';
            node.innerHTML = `<p class="metric-label">${label}</p>` +
                `<p class="metric-value">${shown}</p><p class="metric-hint">${hint}</p>`;
            return node;
        }), 4);
        qs('#ratesLine').textContent = F.ratesLine(period.exchange);
        qs('#notices').innerHTML = F.noticesHtml(period.notices.concat(data.notices));
    }

    try {
        const data = await F.report();
        F.periodSelect(qs('#periodSelect'), data, (period) => render(period, data));
        F.explain('finance_balance', () => shown, qs('.period-bar'));
    } catch (error) {
        toast(F.errorText(error, 'No se pudo leer el Balance General.'), 'error');
    }
});
