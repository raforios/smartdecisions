'use strict';

/** Estado de Resultados of the chosen month or year, in the three currencies. */
document.addEventListener('DOMContentLoaded', async () => {
    if (!window.SD_AUTH.isAuthenticated()) return;

    const F = window.SD_FINANCE;
    const { qs, toast } = window.SD_UI;

    function render(period, data) {
        const statement = period.income_statement;
        qs('#statementTable tbody').innerHTML = F.STATEMENT_LINES
            .filter(([key]) => statement[key])
            .map(([key, label, total]) => F.moneyRow(label, statement[key], period.exchange, total))
            .join('');
        qs('#ratesLine').textContent = F.ratesLine(period.exchange);
        qs('#notices').innerHTML = F.noticesHtml(period.notices.concat(data.notices));
    }

    try {
        const data = await F.report();
        F.periodSelect(qs('#periodSelect'), data, (period) => render(period, data));
    } catch (error) {
        toast(F.errorText(error, 'No se pudo leer el Estado de Resultados.'), 'error');
    }
});
