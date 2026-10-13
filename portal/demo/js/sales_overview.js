'use strict';

/**
 * Comercial › Ventas — one block per option with the figure that says the
 * most about it. Each answer is kept in the same cache the option pages read,
 * so opening an option from here shows it at once instead of computing it
 * again. Blocks paint as their answers arrive: the slowest analyses take
 * several seconds and must not hold the others.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.isAuthenticated()) return;
    const A = window.SD_ANALYSIS;
    const M = window.SD_MONEY;
    const BASE = `${window.SD_CONFIG.ANALYTICS_URL}/v1/analytics`;
    const qs = (selector) => document.querySelector(selector);
    const tile = (name) => qs(`[data-tile="${name}"]`);

    const TITLES = {
        summary: 'Resumen comercial', volume: 'Fuente de volumen', opportunities: 'Oportunidades',
        forecast: 'Pronóstico de demanda', segmentation: 'Segmentación de clientes',
        portfolio: 'Salud de cartera', objectives: 'Cumplimiento de objetivos',
        fx: 'Efecto del tipo de cambio'
    };
    const MONTHS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
        'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];

    const token = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    const number = (value, decimals = 0) => (value == null ? '—'
        : Number(value).toLocaleString('es-BO', {
            minimumFractionDigits: decimals, maximumFractionDigits: decimals }));
    const signed = (value) => `${value > 0 ? '+' : ''}${number(value, 1)} %`;
    const day = (iso) => {
        const [year, month, date] = String(iso || '').split('-');
        return MONTHS[Number(month) - 1] ? `${Number(date)} de ${MONTHS[Number(month) - 1]} de ${year}` : '';
    };
    const kpi = (kpis, code) => ((kpis || []).find((card) => card.metric_code === code) || {}).value;

    /** Title, figure, one line and an optional small visual. */
    function paint(name, value, line, visual = '') {
        tile(name).innerHTML = `<p class="sd-tile-title">${TITLES[name]}</p>` +
            `<p class="sd-tile-value">${value}</p><p class="sd-tile-line">${line}</p>` +
            (visual ? `<div class="sd-tile-visual">${visual}</div>` : '');
    }

    /** A bar split in shares, with its legend under it. */
    function shares(parts) {
        return `<div class="sd-bar">${parts.map(([, share, color]) =>
            `<span style="width:${Math.max(share, 0)}%;background:${color}"></span>`).join('')}</div>` +
            `<div class="sd-bar-legend">${parts.map(([label, share, color]) =>
                `<span><i style="background:${color}"></i>${label} ${number(share, 1)} %</span>`).join('')}</div>`;
    }

    function progress(percent) {
        return `<div class="sd-progress"><span style="width:${Math.min(Math.max(percent, 0), 100)}%"></span></div>`;
    }

    function loading() {
        document.querySelectorAll('[data-tile]').forEach((node) => {
            node.innerHTML = `<p class="sd-tile-title">${TITLES[node.dataset.tile]}</p>` +
                '<span class="sd-skeleton is-big"></span><span class="sd-skeleton"></span>';
        });
    }

    function failed(name) {
        paint(name, '—', 'No se pudo calcular. Entra para volver a intentar.');
    }

    // ---------- each option ----------
    function summary(data) {
        const total = kpi(data.kpis, 'TOTAL_SALES');
        const period = data.period || {};
        const from = period.filtered ? period.from_date : period.available_from;
        const to = period.filtered ? period.to_date : period.available_to;
        if (from && to) qs('#salesWhen').textContent = `Del ${day(from)} al ${day(to)}.`;
        tile('summary').innerHTML =
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
        const headline = volume.headline || {};
        if (!classA) {
            paint('volume', '—', 'Sin productos para clasificar.');
            return;
        }
        paint('volume', `${number(classA.products)} productos`,
            `hacen el ${number(classA.percentage, 1)} % de la venta, de ${number(headline.total_products)}.`,
            shares((volume.abc_summary || []).map((row, index) => [`Clase ${row.abc_class}`,
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
            shares(tiers.map((tier) => [labels[tier.tier] || tier.tier, tier.percentage, colors[tier.tier]])));
    }

    function portfolio(data) {
        const atRisk = kpi(data.kpis, 'CLIENTS_AT_RISK');
        paint('portfolio', `${number(atRisk)} en riesgo`,
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
            progress(invoiced));
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

    /** One analysis: the cached answer, or a fresh one that is then cached. */
    function analysis(kind, path, render) {
        const cached = A.cachedResult(kind);
        if (cached) {
            render(cached.payload);
            return;
        }
        window.SD_API.get(path).then((payload) => {
            A.cacheResult(kind, payload);
            render(payload);
        }).catch(() => (kind === 'summary' ? ['summary', 'volume'] : [kind]).forEach(failed));
    }

    async function load() {
        loading();
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
        analysis('summary', `${BASE}/summary/${id}${query}`, summary);
        analysis('segmentation', `${BASE}/segmentation/${id}${query}`, segmentation);
        analysis('portfolio', `${BASE}/portfolio/${id}${query}`, portfolio);
        analysis('objectives', `${BASE}/objectives/${id}${query}`, objectives);
        analysis('fx', `${BASE}/fx-effect/${id}${fxQuery}`, fx);
        window.SD_API.get(`${BASE}/runs`, { limit: 5 })
            .then((runs) => opportunities(runs, datasetId))
            .catch(() => failed('opportunities'));
        paint('forecast', 'Próximos meses', 'Se calcula al abrir, total o por categoría, con el método que elijas.');
    }

    load();
});
