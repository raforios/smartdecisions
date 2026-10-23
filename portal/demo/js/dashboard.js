'use strict';

/**
 * Principal — how the business stands, area by area, with the way into each
 * area behind its block.
 *
 * ANALYTICS answers the figures (`/dashboard`), the monthly sales (`/summary`)
 * and the credit book by age (`/receivables`); OPTIMIZATION answers the field.
 * Each block paints as its answer arrives, so a slow analysis never holds the
 * rest of the page. What is held today (stock, receivables) reads at today's
 * rate; a month, at its close.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.isAuthenticated() || window.SD_AUTH.getRole() === 'SELLER') return;
    const { API_URL } = window.SD_CONFIG;
    const M = window.SD_MONEY;
    const icon = window.SD_ICONS.svg;
    const qs = (selector) => document.querySelector(selector);

    const MONTHS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
        'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
    // The credit book in four ages: my own grouping of the seven buckets
    // ANALYTICS sends, so the ring stays readable.
    const AGES = [
        { label: 'Por vencer', buckets: ['CURRENT'], color: '--accent-2' },
        { label: 'Vencido hasta 30 días', buckets: ['DAYS_1_15', 'DAYS_16_30'], color: '--accent' },
        { label: 'De 31 a 90 días', buckets: ['DAYS_31_60', 'DAYS_61_90'], color: '--warning' },
        { label: 'Más de 90 días', buckets: ['DAYS_91_120', 'DAYS_OVER_120'], color: '--danger' }
    ];
    const ERRORS = {
        RATES_UNAVAILABLE: 'No hay tipo de cambio de hoy: el servicio de cotizaciones no ' +
            'respondió. Vuelve a intentar en unos minutos.',
        RATES_STORE_UNAVAILABLE: 'No se pudieron leer los tipos de cambio guardados. ' +
            'Vuelve a intentarlo en unos minutos.'
    };
    const state = { trend: [], months: 12, currency: 'BOB', charts: {} };

    const token = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    const number = (value, decimals = 0) => (value == null ? '—'
        : Number(value).toLocaleString('es-BO', {
            minimumFractionDigits: decimals, maximumFractionDigits: decimals }));
    const monthName = (key, withYear = true) => {
        const [year, month] = String(key || '').split('-');
        const name = MONTHS[Number(month) - 1];
        if (!name) return key || '';
        return withYear ? `${name} de ${year}` : `${name.slice(0, 3)} ${year.slice(2)}`;
    };
    const isoDay = (offset) => {
        const day = new Date(Date.now() + offset * 86400000);
        return [day.getFullYear(), String(day.getMonth() + 1).padStart(2, '0'),
            String(day.getDate()).padStart(2, '0')].join('-');
    };
    const bob = (money) => `Bs ${number(money && money.bob)}`;
    const others = (money) => `USD ${number(money && money.usd)} | USDT ${number(money && money.usdt)}`;

    function change(value, against) {
        if (value == null) return '';
        const kind = value > 0 ? 'is-up' : (value < 0 ? 'is-down' : '');
        return `<span class="sd-change ${kind}">${value > 0 ? '+' : ''}${number(value, 1)} % ` +
            `${against}</span>`;
    }

    function stat(iconName, label, money, note, noteKind = '') {
        return `<span class="sd-stat-icon">${icon(iconName)}</span>` +
            `<p class="sd-stat-label">${label}</p>` +
            `<p class="sd-stat-value">${bob(money)}</p>` +
            `<p class="sd-stat-other">${others(money)}</p>` +
            `<p class="sd-stat-note ${noteKind}">${note}</p>`;
    }

    function list(rows) {
        return rows.map(([label, value, bad]) =>
            `<div class="sd-list-row"><span>${label}</span>` +
            `<b class="${bad ? 'is-bad' : ''}">${value}</b></div>`).join('');
    }

    function paintFigures(data) {
        const sales = data.sales || {};
        if (!sales.month) {
            qs('#overviewTop').hidden = true;
            qs('#overviewEmpty').hidden = false;
            return;
        }
        qs('#overviewWhen').textContent = `Venta de ${monthName(sales.month)}, cada mes a su ` +
            'cierre. Stock y cobranza, a hoy.';
        if (data.rates) {
            const rates = qs('#overviewRates');
            rates.innerHTML = `<span>Dólar oficial <b>Bs ${number(data.rates.usd, 2)}</b></span>` +
                `<span>USDT <b>Bs ${number(data.rates.usdt, 2)}</b></span>` +
                `<span>Brecha <b>${number(data.fx_gap, 2)} %</b></span>`;
            rates.hidden = false;
        }

        qs('#heroSales').innerHTML =
            `<p class="sd-hero-label">Venta de ${monthName(sales.month)}</p>` +
            `<p class="sd-hero-value">${bob(sales.amount)}</p>` +
            `<div class="sd-hero-other"><span>USD<b>${number(sales.amount && sales.amount.usd)}</b></span>` +
            `<span>USDT<b>${number(sales.amount && sales.amount.usdt)}</b></span>` +
            `<span>Objetivo<b>${sales.attainment == null ? 'sin objetivos'
                : `${number(sales.attainment, 1)} %`}</b></span>` +
            `<span>Margen bruto<b>${sales.gross_margin_percent == null ? 'sin costos'
                : `${number(sales.gross_margin_percent, 1)} %`}</b></span></div>` +
            `<div class="sd-hero-foot">${change(sales.change_vs_previous, 'vs mes anterior')}` +
            `${change(sales.change_vs_last_year, 'vs mismo mes del año pasado')}</div>`;

        const book = data.receivables || {};
        qs('#statReceivables').innerHTML = book.available
            ? stat('receivables', 'Por cobrar hoy', book.balance,
                `${number(book.overdue_rate, 1)} % vencido`, book.overdue_rate > 0 ? 'is-bad' : '')
            : stat('receivables', 'Por cobrar hoy', null, 'Sin ventas a crédito');
        const stock = data.inventory || {};
        qs('#statStock').innerHTML = stock.available
            ? stat('stock', 'Valor del stock hoy', stock.value,
                `${number(stock.out_of_stock)} agotados, ${number(stock.at_risk)} por agotarse`,
                stock.out_of_stock > 0 ? 'is-bad' : '')
            : stat('stock', 'Valor del stock hoy', null, 'Sin foto de stock');
        const purchases = data.purchases || {};
        qs('#statPurchases').innerHTML = purchases.available
            ? stat('purchases', `Compras de ${monthName(purchases.month)}`, purchases.amount,
                `Costo subió en ${number(purchases.cost_up)} productos, bajó en ${number(purchases.cost_down)}`)
            : stat('purchases', 'Compras del mes', null, 'Sin compras cargadas');
        qs('#overviewTop').hidden = false;

        const clients = data.clients || {};
        qs('#listClients').innerHTML = list([
            ['Compraron en el mes', number(clients.bought_this_month)],
            ['En riesgo de perderse', number(clients.at_risk), clients.at_risk > 0],
            ['Nuevos en el mes', number(clients.new_clients)],
            ['Perdidos', number(clients.lost), clients.lost > 0],
            ['Venta que hace el 20 % mayor', clients.top_fifth_share == null ? '—'
                : `${number(clients.top_fifth_share, 1)} %`]
        ]);
        qs('#overviewLists').hidden = false;
        qs('#overviewCharts').hidden = false;
    }

    function paintTrend() {
        const points = state.months ? state.trend.slice(-state.months) : state.trend;
        qs('#trendEmpty').hidden = points.length > 0;
        if (!window.Chart || !points.length) return;
        if (state.charts.trend) state.charts.trend.destroy();
        const accent = token('--accent');
        state.charts.trend = new window.Chart(qs('#trendChart'), {
            type: 'bar',
            data: {
                labels: points.map((point) => monthName(point.month, false)),
                datasets: [{
                    data: points.map((point) => M.pick(point.amount, state.currency)),
                    // The last month is the one the hero talks about.
                    backgroundColor: points.map((_, index) =>
                        (index === points.length - 1 ? token('--accent-2') : accent)),
                    borderRadius: 6,
                    maxBarThickness: 36
                }]
            },
            options: {
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: { callbacks: { label: (item) =>
                        `${{ BOB: 'Bs', USD: 'USD', USDT: 'USDT' }[state.currency]} ${number(item.raw)}` } }
                },
                scales: {
                    x: { grid: { display: false }, border: { display: false } },
                    y: { border: { display: false }, grid: { color: token('--bg-alt') },
                         ticks: { callback: (value) => number(value / 1000) + ' mil' } }
                }
            }
        });
    }

    function paintAging(book) {
        const rows = (book && book.available && book.aging) || [];
        const groups = AGES.map((age) => ({
            ...age,
            amount: rows.filter((row) => age.buckets.includes(row.bucket_code))
                .reduce((sum, row) => M.add(sum, row.amount), 0)
        }));
        const total = groups.reduce((sum, group) => sum + M.bob(group.amount), 0);
        qs('#agingEmpty').hidden = total > 0;
        if (!total || !window.Chart) return;
        qs('#agingRing').hidden = false;
        qs('#agingTotal').textContent = `Bs ${number(total)}`;
        state.charts.aging = new window.Chart(qs('#agingChart'), {
            type: 'doughnut',
            data: {
                labels: groups.map((group) => group.label),
                datasets: [{
                    data: groups.map((group) => M.bob(group.amount)),
                    backgroundColor: groups.map((group) => token(group.color)),
                    borderWidth: 0
                }]
            },
            options: {
                maintainAspectRatio: false,
                cutout: '74%',
                plugins: { legend: { display: false },
                    tooltip: { callbacks: { label: (item) => ` Bs ${number(item.raw)}` } } }
            }
        });
        qs('#agingLegend').innerHTML = groups.map((group) =>
            `<div class="sd-legend-row"><span class="sd-dot" style="background:${token(group.color)}"></span>` +
            `<span>${group.label}</span><b>${number(100 * M.bob(group.amount) / total, 1)} %</b></div>`)
            .join('');
    }

    async function paintField(rates) {
        const day = (offset) => window.SD_API.get(
            `${API_URL}/v1/commercial/statistics/day/${isoDay(offset)}`).catch(() => null);
        const [today, yesterday] = await Promise.all([day(0), day(-1)]);
        if (!today || !today.routes_started) {
            qs('#fieldEmpty').hidden = false;
            if (!yesterday) return;
        }
        const sale = today && today.sales_amount != null && rates
            ? M.atRates(today.sales_amount, rates) : null;
        qs('#listField').innerHTML = list([
            ['Vendedores en la calle', number(today && today.sellers_on_route)],
            ['Rutas cerradas de las iniciadas', today
                ? `${number(today.routes_closed)} de ${number(today.routes_started)}` : '—'],
            ['Visitas cumplidas ayer', !yesterday || yesterday.visit_compliance == null
                ? 'sin plan' : `${number(yesterday.visit_compliance, 1)} %`],
            ['Km recorridos hoy', number(today && today.distance_km, 1)],
            ['Venta de hoy en la calle', sale ? `${bob(sale)}<br><small>${others(sale)}</small>` : '—']
        ]);
    }

    /** Grey bars in the top blocks until the figures arrive. */
    function showLoading() {
        const bars = '<span class="sd-skeleton is-short"></span><span class="sd-skeleton is-big"></span>' +
            '<span class="sd-skeleton"></span><span class="sd-skeleton is-short"></span>';
        ['#heroSales', '#statReceivables', '#statStock', '#statPurchases'].forEach((id) => {
            qs(id).innerHTML = bars;
        });
        qs('#overviewTop').hidden = false;
    }

    async function load() {
        showLoading();
        const datasetId = await window.SD_API.ensureDataset();
        if (!datasetId) {
            qs('#overviewTop').hidden = true;
            qs('#overviewEmpty').hidden = false;
            paintField(null);
            return;
        }
        const base = `${API_URL}/v1/commercial`;
        const id = encodeURIComponent(datasetId);
        const data = await window.SD_API.get(`${base}/dashboard/${id}`).catch((error) => {
            const empty = qs('#overviewEmpty');
            empty.textContent = ERRORS[error && error.code] || 'No se pudo armar el resumen.';
            empty.hidden = false;
            qs('#overviewTop').hidden = true;
            return null;
        });
        if (data) paintFigures(data);
        paintField(data && data.rates);
        window.SD_API.get(`${base}/summary/${id}`).then((summary) => {
            state.trend = (summary && summary.monthly_trend) || [];
            paintTrend();
        }).catch(() => { qs('#trendEmpty').hidden = false; });
        window.SD_API.get(`${base}/receivables/${id}`).then(paintAging)
            .catch(() => { qs('#agingEmpty').hidden = false; });
    }

    qs('#trendRange').addEventListener('click', (event) => {
        const button = event.target.closest('button');
        if (!button) return;
        state.months = Number(button.dataset.months);
        document.querySelectorAll('#trendRange button').forEach((other) =>
            other.classList.toggle('is-active', other === button));
        paintTrend();
    });
    qs('#trendCurrency').addEventListener('change', (event) => {
        state.currency = event.target.value;
        paintTrend();
    });
    load();
});
