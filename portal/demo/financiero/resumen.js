'use strict';

/**
 * Resumen: the owner's questions of the plan, answered with the figures of
 * the chosen period, and the months side by side in a chart.
 */
document.addEventListener('DOMContentLoaded', async () => {
    if (!window.SD_AUTH.isAuthenticated()) return;

    const F = window.SD_FINANCE;
    const { qs, toast } = window.SD_UI;
    const css = getComputedStyle(document.documentElement);
    const color = (name) => css.getPropertyValue(name).trim();

    const number = (value, decimals) => value == null ? '—'
        : value.toLocaleString('es-BO', { minimumFractionDigits: decimals,
                                           maximumFractionDigits: decimals });

    function card(question, valueHtml, hint, variant) {
        const node = document.createElement('div');
        node.className = 'metric';
        node.innerHTML = `<p class="metric-label">${question}</p>` +
            (variant !== undefined
                ? `<div class="metric-value ${variant}">${valueHtml}</div>` : valueHtml) +
            (hint ? `<p class="metric-hint">${hint}</p>` : '');
        return node;
    }

    // What the AI reads: the chosen period, the months of the chart and the
    // report's notices, as the backend returned them.
    let shown = null;

    function render(period, data) {
        shown = { period, months: data.months, notices: data.notices };
        const statement = period.income_statement;
        const at = (amount) => window.SD_MONEY.card(F.money(amount, period.exchange));
        const profit = statement.profit_before_income_tax.amount;
        const indicators = period.indicators;
        F.arrange(qs('#answers'), [
            card('¿Tengo utilidades?', at(profit),
                 profit == null ? '' : (profit >= 0
                     ? 'Utilidad antes del IUE: el negocio gana.'
                     : 'Pérdida antes del IUE: el negocio gasta más de lo que gana.')),
            card('¿Cuánto vendí, ya sin impuestos?', at(statement.net_sales.amount),
                 'Ventas menos el IVA y el IT.'),
            card('¿Cuánto efectivo tengo?', at(period.balance.cash),
                 'Caja, bancos y billeteras al cierre.'),
            card('¿Hasta cuándo llego sin vender?',
                 `<p class="metric-value">${number(indicators.coverage_months, 1)} meses</p>`,
                 'Efectivo frente a lo que sale en un mes, en promedio.'),
            card('¿Puedo pagar lo que vence pronto?',
                 `<p class="metric-value">${number(indicators.liquidity, 2)}</p>`,
                 'Activo corriente por cada boliviano de pasivo corriente: más de 1, alcanza.'),
            card('¿Cuánto de lo que tengo es deuda?',
                 `<p class="metric-value">${indicators.debt_ratio == null ? '—'
                     : `${number(indicators.debt_ratio * 100, 0)} %`}</p>`,
                 'Pasivo frente al activo.')
        ]);

        qs('#ratesLine').textContent = F.ratesLine(period.exchange);
        qs('#notices').innerHTML = F.noticesHtml(period.notices.concat(data.notices));
    }

    function chart(data) {
        if (!window.Chart) return;
        const months = data.months;
        const line = (key) => months.map((p) => p.income_statement[key].amount);
        const profit = line('profit_before_income_tax');
        const sales = line('net_sales');
        window.Chart.defaults.maintainAspectRatio = false;
        window.Chart.defaults.locale = 'es-BO';
        new window.Chart(qs('#trendChart'), {
            type: 'bar',
            data: {
                labels: months.map((p) => F.periodLabel(p.period)),
                datasets: [
                    { label: 'Ventas netas', data: sales, backgroundColor: color('--accent') },
                    { label: 'Egresos', data: sales.map((value, i) => value - profit[i]),
                      backgroundColor: color('--muted') },
                    { label: 'Utilidad', data: profit, type: 'line',
                      borderColor: color('--success'), backgroundColor: color('--success') }
                ]
            },
            options: { responsive: true, plugins: { legend: { position: 'bottom' } } }
        });
    }

    try {
        const data = await F.report();
        if (!data.months.length && !data.years.length) {
            qs('#notices').innerHTML =
                '<li>Todavía no cargaste datos. Empieza en «Cargar datos».</li>';
            return;
        }
        F.periodSelect(qs('#periodSelect'), data, (period) => render(period, data));
        F.explain('finance_summary', () => shown, qs('.period-bar'));
        chart(data);
    } catch (error) {
        toast(F.errorText(error, 'No se pudo leer el análisis financiero.'), 'error');
    }
});
