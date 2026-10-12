'use strict';

/**
 * Segmentación de clientes by the value of what they buy.
 */
(function (A) {
    if (!window.SD_AUTH.isAuthenticated()) return;
    const { qs, qsAll, toast, setButtonBusy } = window.SD_UI;

    // ---------- Segmentation ----------
    // The backend reports the tier as a code; the colour and the Spanish
    // wording live here, like every other label.
    const TIER_COLOR = { HIGH: '#2d7d46', MEDIUM: '#c4a378', LOW: '#c0392b' };
    const TIER_LABELS = { HIGH: 'Alto', MEDIUM: 'Medio', LOW: 'Bajo' };

    function tierLabel(code) {
        return TIER_LABELS[code] || code || '';
    }
    let segmentClients = [];
    let segmentTotal = 0;
    let segmentAllClients = 0;

    function renderSegmentation(data) {
        const tiers = data.tiers || [];
        segmentClients = data.clients || [];
        // Shares are decided in bolivianos: the rate never reorders clients.
        segmentTotal = tiers.reduce((sum, tier) => sum + window.SD_MONEY.bob(tier.amount), 0);
        segmentAllClients = data.total_clients || segmentClients.length;

        // KPI per tier: client count + sales share.
        const kpiBox = qs('#segmentKpis');
        kpiBox.innerHTML = '';
        kpiBox.appendChild(A.metricCard({
            label: 'Clientes totales', value: A.formatInt(data.total_clients || 0)
        }));
        tiers.forEach((tier) => kpiBox.appendChild(A.metricCard({
            label: `Segmento ${tierLabel(tier.tier)}`,
            value: `${A.formatInt(tier.clients)} · ${A.formatDecimal(tier.percentage, 1)}%`,
            hint: `${A.formatCurrency(tier.amount)} de venta`
        })));
        A.arrangeMetrics(kpiBox);

        // Doughnut of sales share by tier.
        A.makeChart('chartSegmentos', {
            type: 'doughnut',
            data: {
                labels: tiers.map(
                    (t) => `${tierLabel(t.tier)} (${A.formatDecimal(t.percentage, 1)}%)`
                ),
                datasets: [{ data: tiers.map((t) => A.chartAmount(t.amount)),
                    backgroundColor: tiers.map((t) => TIER_COLOR[t.tier] || A.BRAND[0]) }]
            },
            options: { responsive: true, plugins: { legend: { position: 'right' } } }
        });

        renderSegmentTable();
        A.showAnalysisView('stepSegmentation');
    }

    function filteredSegmentClients() {
        const tier = qs('#segmentFilter').value;
        const search = qs('#segmentSearch').value.trim().toLowerCase();
        return segmentClients.filter((client) =>
            (!tier || client.tier === tier) &&
            (!search || String(client.client).toLowerCase().includes(search)));
    }

    function renderSegmentTable() {
        const rows = filteredSegmentClients();
        A.fillTable('segmentTable', rows, (client, position) => {
            const purchases = Number(client.purchases) || 0;
            const amount = client.amount;
            const ticket = {};
            ['bob', 'usd', 'usdt'].forEach((key) => {
                const value = amount && typeof amount === 'object' ? amount[key] : amount;
                ticket[key] = purchases && value != null ? value / purchases : null;
            });
            const share = segmentTotal
                ? (window.SD_MONEY.bob(amount) / segmentTotal) * 100 : 0;
            return `<td class="rank-cell">${position + 1}</td>` +
                `<td>${A.escapeHtml(client.client)}</td>` +
                `<td><span class="tier-badge tier-${client.tier}">` +
                `${A.escapeHtml(tierLabel(client.tier))}</span></td>` +
                `<td class="numeric">${A.formatInt(purchases)}</td>` +
                window.SD_MONEY.cells(amount, 2, 'strong') +
                window.SD_MONEY.cells(ticket) +
                `<td class="numeric">${A.formatDecimal(share, 2)}%</td>`;
        }, { emptyText: 'Sin clientes para ese filtro.' });
        // The API caps the client list, so say so instead of letting the user
        // wonder why the lowest tier looks smaller than its KPI card.
        qs('#segmentCount').textContent = segmentClients.length < segmentAllClients
            ? `${A.formatInt(rows.length)} en pantalla · se listan los ` +
              `${A.formatInt(segmentClients.length)} clientes de mayor valor ` +
              `de ${A.formatInt(segmentAllClients)}`
            : `${A.formatInt(rows.length)} cliente(s)`;
    }

    qs('#segmentFilter').addEventListener('change', renderSegmentTable);
    qs('#segmentSearch').addEventListener('input', renderSegmentTable);

    Object.assign(A, {
        renderSegmentation
    });
})(window.SD_ANALYSIS = window.SD_ANALYSIS || {});
