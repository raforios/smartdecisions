'use strict';

/**
 * Comercial › Ventas — one block per option with the figure that says the
 * most about it. Blocks paint as their answers arrive: the slowest analyses
 * take several seconds and must not hold the others.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.isAuthenticated()) return;
    const A = window.SD_ANALYSIS;
    const M = window.SD_MONEY;
    const O = window.SD_OVERVIEW;
    const { number, signed, kpi, token } = O;
    const BASE = `${window.SD_CONFIG.ANALYTICS_URL}/v1/analytics`;
    const qs = (selector) => document.querySelector(selector);

    const TITLES = {
        summary: 'Resumen comercial', volume: 'Fuente de volumen', opportunities: 'Oportunidades',
        forecast: 'Pronóstico de demanda', segmentation: 'Segmentación de clientes',
        portfolio: 'Salud de cartera', objectives: 'Cumplimiento de objetivos',
        fx: 'Efecto del tipo de cambio'
    };
    const paint = (name, ...rest) => O.paint(name, TITLES[name], ...rest);
    const failed = (name) => paint(name, '—', 'No se pudo calcular. Entra para volver a intentar.');

    function summary(data) {
        const total = kpi(data.kpis, 'TOTAL_SALES');
        const period = data.period || {};
        const from = period.filtered ? period.from_date : period.available_from;
        const to = period.filtered ? period.to_date : period.available_to;
        if (from && to) qs('#salesWhen').textContent = `Del ${O.day(from)} al ${O.day(to)}.`;
        O.tile('summary').innerHTML =
            `<p class="sd-hero-label">${TITLES.summary}: venta del período</p>` +
            `<p class="sd-hero-value">Bs ${number(M.bob(total))}</p>` +
            `<div class="sd-hero-other"><span>USD<b>${number(total && total.usd)}</b></span>` +
            `<span>USDT<b>${number(total && total.usdt)}</b></span>` +
            `<span>Ventas<b>${number(kpi(data.kpis, 'SALES_COUNT'))}</b></span>` +
            `<span>Ticket promedio<b>Bs ${number(M.bob(kpi(data.kpis, 'AVERAGE_TICKET')))}</b></span></div>` +
            '<div class="sd-spark"><canvas id="salesSpark"></canvas></div>';
        sparkline(data.monthly_trend || []);

        const volume = data.volume_source || {};
        const classA = (volume.abc_summary || []).find((row) => row.abc_class === 'A');
        if (!classA) {
            paint('volume', '—', 'Sin productos para clasificar.');
            return;
        }
        paint('volume', `${number(classA.products)} productos`,
            `hacen el ${number(classA.percentage, 1)} % de la venta, de ` +
            `${number((volume.headline || {}).total_products)}.`,
            O.shares((volume.abc_summary || []).map((row, index) => [`Clase ${row.abc_class}`,
                row.percentage, [token('--accent-2'), token('--accent'), token('--border-strong')][index]])));
    }

    function sparkline(points) {
        if (!window.Chart || points.length < 2) return;
        new window.Chart(qs('#salesSpark'), {
            type: 'line',
            data: { labels: points.map((point) => point.month),
                datasets: [{ data: points.map((point) => M.bob(point.amount)), borderColor: '#7fd6cb',
                             borderWidth: 2, pointRadius: 0, tension: 0.35, fill: false }] },
            options: { maintainAspectRatio: false, animation: false,
                plugins: { legend: { display: false }, tooltip: { enabled: false } },
                scales: { x: { display: false }, y: { display: false } } }
        });
    }

    function segmentation(data) {
        const tiers = data.tiers || [];
        const high = tiers.find((tier) => tier.tier === 'HIGH');
        if (!high) {
            paint('segmentation', '—', 'Sin clientes para clasificar.');
            return;
        }
        const colors = { HIGH: token('--accent-2'), MEDIUM: token('--accent'), LOW: token('--border-strong') };
        const labels = { HIGH: 'Alto', MEDIUM: 'Medio', LOW: 'Bajo' };
        paint('segmentation', `${number(high.clients)} clientes`,
            `de valor alto hacen el ${number(high.percentage, 1)} % de la venta.`,
            O.shares(tiers.map((tier) => [labels[tier.tier] || tier.tier, tier.percentage, colors[tier.tier]])));
    }

    function portfolio(data) {
        paint('portfolio', `${number(kpi(data.kpis, 'CLIENTS_AT_RISK'))} en riesgo`,
            `${number(kpi(data.kpis, 'CLIENTS_LOST'))} perdidos. ` +
            `Compraron ${number(kpi(data.kpis, 'ACTIVE_LAST_MONTH'))} de ` +
            `${number(kpi(data.kpis, 'PORTFOLIO_CLIENTS'))} el último mes.`);
    }

    function objectives(data) {
        const totals = data.totals;
        if (!totals || totals.invoiced_ratio == null) {
            paint('objectives', '—', 'Sin objetivos cargados.');
            return;
        }
        const invoiced = 100 * totals.invoiced_ratio;
        paint('objectives', `${number(invoiced, 1)} %`,
            `facturado del objetivo; cobrado ${number(100 * totals.collected_ratio, 1)} %.`,
            O.progress(invoiced));
    }

    function fx(data) {
        if (data.growth_bob_pct == null) {
            paint('fx', '—', 'Sin meses para comparar.');
            return;
        }
        paint('fx', `${signed(data.growth_bob_pct)} en Bs`,
            `${signed(data.growth_usd_pct)} medido en dólares, del primer al último mes.`);
    }

    function opportunities(runs, datasetId) {
        const run = ((runs && runs.runs) || []).find((item) => item.dataset_id === datasetId);
        if (!run) {
            paint('opportunities', 'Sin calcular', 'Se calculan al abrir; tardan cerca de medio minuto.');
            return;
        }
        paint('opportunities', `${number(run.total_opportunities)}`,
            `oportunidades en ${number(run.total_pos_with_opportunities)} clientes, ` +
            `valor esperado Bs ${number(M.bob(run.total_expected_value))}.`);
    }

    async function load() {
        O.loading(TITLES);
        const datasetId = await window.SD_API.ensureDataset();
        if (!datasetId) {
            qs('#salesTiles').hidden = true;
            qs('#salesEmpty').hidden = false;
            return;
        }
        const id = encodeURIComponent(datasetId);
        const query = A.periodQuery(A.readStoredPeriod());
        // The exchange-rate view reads the official dollar unless told otherwise,
        // the same default its own page starts with.
        const fxQuery = query ? `${query}&source=USD` : '?source=USD';
        O.analysis('summary', `${BASE}/summary/${id}${query}`, summary,
            () => { failed('summary'); failed('volume'); });
        O.analysis('segmentation', `${BASE}/segmentation/${id}${query}`, segmentation,
            () => failed('segmentation'));
        O.analysis('portfolio', `${BASE}/portfolio/${id}${query}`, portfolio, () => failed('portfolio'));
        O.analysis('objectives', `${BASE}/objectives/${id}${query}`, objectives, () => failed('objectives'));
        O.analysis('fx', `${BASE}/fx-effect/${id}${fxQuery}`, fx, () => failed('fx'));
        window.SD_API.get(`${BASE}/runs`, { limit: 5 })
            .then((runs) => opportunities(runs, datasetId))
            .catch(() => failed('opportunities'));
        paint('forecast', 'Próximos meses', 'Se calcula al abrir, total o por categoría, con el método que elijas.');
    }

    load();
});
