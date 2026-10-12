'use strict';

/**
 * Salud de cartera: who stopped buying and who is at risk.
 */
(function (A) {
    if (!window.SD_AUTH.isAuthenticated()) return;
    const { qs, qsAll, toast, setButtonBusy } = window.SD_UI;

    // ---------- Portfolio health ----------
    let riskClients = [];

    function renderPortfolio(data) {
        A.fillKpis('portfolioKpis', data.kpis, (card) =>
            card.metric_code === 'CLIENTS_AT_RISK' ? 'warning' : '');

        const movement = data.movement || [];
        A.makeChart('chartMovement', {
            type: 'bar',
            data: {
                labels: movement.map((row) => row.month),
                datasets: [
                    {
                        label: 'Nuevos', data: movement.map((row) => row.new_clients),
                        backgroundColor: A.BRAND[3]
                    },
                    {
                        label: 'Recuperados', data: movement.map((row) => row.recovered),
                        backgroundColor: A.BRAND[2]
                    },
                    {
                        label: 'Perdidos', data: movement.map((row) => -row.lost),
                        backgroundColor: '#c0392b'
                    }
                ]
            },
            options: {
                responsive: true,
                plugins: { legend: { position: 'bottom' } },
                scales: { x: { stacked: true }, y: { stacked: true } }
            }
        });

        A.makeChart('chartActive', {
            type: 'line',
            data: {
                labels: movement.map((row) => row.month),
                datasets: [{
                    label: 'Clientes activos', data: movement.map((row) => row.active),
                    borderColor: A.BRAND[0], backgroundColor: 'rgba(13,30,76,0.1)',
                    fill: true, tension: 0.3
                }]
            },
            // Counts are anchored at zero on purpose: letting Chart.js pick the
            // range turned a 9-client change into a visual cliff, which reads as
            // a collapse the data does not support.
            options: {
                ...chartOptions('int'),
                scales: { y: { beginAtZero: true } }
            }
        });

        riskClients = data.at_risk || [];
        renderRiskTable();

        // Kept in its own table: a client gone half a year is a campaign, not a
        // visit, and mixing them buries the names worth chasing this week.
        const lost = data.lost || [];
        qs('#lostCard').hidden = lost.length === 0;
        A.fillTable('lostTable', lost, (row) =>
            `<td>${A.escapeHtml(row.client)}</td>` +
            window.SD_MONEY.cells(row.monthly_average_amount) +
            `<td class="numeric">${A.escapeHtml(row.last_purchase || '—')}</td>` +
            `<td class="numeric">${A.formatInt(row.days_without_purchase)}</td>`);

        A.showAnalysisView('stepPortfolio');
    }

    function renderRiskTable() {
        const term = (qs('#riskSearch').value || '').trim().toLowerCase();
        const rows = term
            ? riskClients.filter((row) => (row.client || '').toLowerCase().includes(term))
            : riskClients;
        A.fillTable('riskTable', rows, (row) =>
            `<td>${A.escapeHtml(row.client)}</td>` +
            window.SD_MONEY.cells(row.monthly_average_amount) +
            window.SD_MONEY.cells(row.last_month_amount) +
            `<td class="numeric ${A.deltaClass(row.change)}">${A.formatDelta(row.change)}</td>` +
            `<td class="numeric">${A.formatInt(row.days_without_purchase)}</td>` +
            `<td class="cell-note">${A.escapeHtml(A.riskReasonText(row))}</td>`);
    }

    qs('#riskSearch').addEventListener('input', renderRiskTable);

    Object.assign(A, {
        renderPortfolio
    });
})(window.SD_ANALYSIS = window.SD_ANALYSIS || {});
