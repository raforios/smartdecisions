'use strict';

/**
 * Tablero principal — the most salient figure of each area, on the area's own
 * card, so the way into the area is the figure itself.
 *
 * ANALYTICS answers every area from the account's dataset; OPTIMIZATION
 * answers the field (sellers out today, yesterday's visits, today's km). A
 * card whose source has nothing to say keeps its description: an empty card
 * would read as a zero, which is a different statement.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.isAuthenticated() || window.SD_AUTH.getRole() === 'SELLER') return;
    const { ANALYTICS_URL, OPTIMIZATION_URL } = window.SD_CONFIG;
    const M = window.SD_MONEY;

    const MONTHS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
        'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
    const monthName = (key) => {
        const [year, month] = String(key || '').split('-');
        return MONTHS[Number(month) - 1] ? `${MONTHS[Number(month) - 1]} de ${year}` : key;
    };
    const number = (value, decimals = 0) => (value == null ? '—'
        : Number(value).toLocaleString('es-BO', {
            minimumFractionDigits: decimals, maximumFractionDigits: decimals }));
    const signed = (value) => (value == null ? '—'
        : `${value > 0 ? '+' : ''}${number(value, 1)} %`);
    const isoDay = (offset) => {
        const day = new Date(Date.now() + offset * 86400000);
        return [day.getFullYear(), String(day.getMonth() + 1).padStart(2, '0'),
            String(day.getDate()).padStart(2, '0')].join('-');
    };

    function fill(area, lines) {
        const box = document.querySelector(`[data-figures="${area}"]`);
        if (!box || !lines.length) return;
        box.innerHTML = lines.map(([label, value]) =>
            `<div class="figure-row"><span class="figure-label">${label}</span>` +
            `<span class="figure-value">${value}</span></div>`).join('');
        box.hidden = false;
    }

    function paint(data) {
        const sales = data.sales || {};
        if (sales.month) {
            fill('ventas', [
                [`Venta de ${monthName(sales.month)}`, M.inline(sales.amount)],
                ['Contra el mes anterior', signed(sales.change_vs_previous)],
                ['Contra el mismo mes del año pasado', signed(sales.change_vs_last_year)],
                ['Cumplimiento del objetivo', sales.attainment == null ? 'sin objetivos'
                    : `${number(sales.attainment, 1)} %`],
                ['Margen bruto', sales.gross_margin_percent == null ? 'sin costos'
                    : `${number(sales.gross_margin_percent, 1)} %`]
            ]);
        }
        const clients = data.clients || {};
        fill('clientes', [
            ['Compraron en el mes', number(clients.bought_this_month)],
            ['En riesgo de perderse', number(clients.at_risk)],
            ['Nuevos · perdidos', `${number(clients.new_clients)} · ${number(clients.lost)}`],
            ['Peso del 20 % mayor', clients.top_fifth_share == null ? '—'
                : `${number(clients.top_fifth_share, 1)} % de la venta`]
        ]);
        const stock = data.inventory || {};
        if (stock.available) {
            fill('inventario', [
                ['Valor del stock (hoy)', M.inline(stock.value)],
                ['Agotados · por agotarse', `${number(stock.out_of_stock)} · ${number(stock.at_risk)}`],
                ['Días de cobertura', number(stock.coverage_days, 1)],
                ['Capital quieto', M.inline(stock.idle_capital)]
            ]);
        }
        const book = data.receivables || {};
        if (book.available) {
            fill('cobranza', [
                ['Saldo por cobrar (hoy)', M.inline(book.balance)],
                ['Vencido', `${number(book.overdue_rate, 1)} %`],
                ['Recuperable', M.inline(book.recoverable)],
                ['Días promedio de cobro', number(book.days_to_collect, 1)]
            ]);
        }
        const purchases = data.purchases || {};
        if (purchases.available) {
            fill('compras', [
                [`Compras de ${monthName(purchases.month)}`, M.inline(purchases.amount)],
                ['Último costo subió · bajó',
                 `${number(purchases.cost_up)} · ${number(purchases.cost_down)} productos`]
            ]);
        }
        if (data.rates) {
            fill('parametros', [
                ['Dólar oficial hoy', `Bs ${number(data.rates.usd, 2)}`],
                ['USDT hoy', `Bs ${number(data.rates.usdt, 2)}`],
                ['Brecha', `${number(data.fx_gap, 2)} %`]
            ]);
        }
    }

    async function field() {
        const day = (offset) => window.SD_API.get(
            `${OPTIMIZATION_URL}/v1/optimization/statistics/day/${isoDay(offset)}`)
            .catch(() => null);
        const [today, yesterday] = await Promise.all([day(0), day(-1)]);
        if (!today && !yesterday) return;
        fill('rutas', [
            ['Vendedores en la calle', number(today && today.sellers_on_route)],
            ['Visitas cumplidas ayer', !yesterday || yesterday.visit_compliance == null
                ? 'sin plan' : `${number(yesterday.visit_compliance, 1)} %`],
            ['Km recorridos hoy', number(today && today.distance_km, 1)],
            ['Venta de hoy en la calle', today && today.sales_amount != null
                ? M.inline(today.sales_amount) : '—']
        ]);
    }

    async function load() {
        const datasetId = await window.SD_API.ensureDataset();
        if (datasetId) {
            window.SD_API.get(`${ANALYTICS_URL}/v1/analytics/dashboard/` +
                `${encodeURIComponent(datasetId)}`).then(paint).catch(() => {
                // The cards keep their description: the areas are still reachable.
            });
        }
        field();
    }

    load();
});
