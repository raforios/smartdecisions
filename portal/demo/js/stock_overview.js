'use strict';

/**
 * Comercial › Inventario — what the stock is worth and what runs out, how its
 * photos changed, and what the sellers carry today.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.isAuthenticated()) return;
    const A = window.SD_ANALYSIS;
    const M = window.SD_MONEY;
    const O = window.SD_OVERVIEW;
    const { number } = O;
    const BASE = `${window.SD_CONFIG.API_URL}/v1/commercial`;
    const qs = (selector) => document.querySelector(selector);

    const TITLES = { stock: 'Stock del día', stockHistory: 'Evolución del inventario', route: 'Stock en ruta' };
    const paint = (name, ...rest) => O.paint(name, TITLES[name], ...rest);
    const failed = (name) => paint(name, '—', 'No se pudo leer. Entra para volver a intentar.');

    function stock(data) {
        const kpis = data.kpis;
        if (!data.available || !kpis) {
            paint('stock', '—', 'Sin foto de stock. Carga el archivo de stock.');
            return;
        }
        qs('#areaWhen').textContent = `Foto del ${O.day(kpis.snapshot_date)}, valorada a hoy.`;
        O.tile('stock').innerHTML =
            `<p class="sd-hero-label">${TITLES.stock}: valor a costo</p>` +
            `<p class="sd-hero-value">Bs ${number(M.bob(kpis.stock_value))}</p>` +
            `<div class="sd-hero-other"><span>USD<b>${number(kpis.stock_value.usd)}</b></span>` +
            `<span>USDT<b>${number(kpis.stock_value.usdt)}</b></span>` +
            `<span>Agotados<b>${number(kpis.out_of_stock)}</b></span>` +
            `<span>Por agotarse<b>${number(kpis.at_risk)}</b></span>` +
            `<span>Días de cobertura<b>${number(kpis.average_coverage_days, 1)}</b></span>` +
            `<span>Capital quieto<b>Bs ${number(M.bob(kpis.excess_value))}</b></span></div>`;
    }

    function history(data) {
        const photos = data.photos || [];
        if (!data.available || !photos.length) {
            paint('stockHistory', '—', 'Sin fotos de stock.');
            return;
        }
        const first = photos[0];
        const last = photos[photos.length - 1];
        paint('stockHistory', `${number(photos.length)} fotos`,
            `Del ${O.day(first.date)} al ${O.day(last.date)}, el valor a costo pasó de ` +
            `Bs ${number(M.bob(first.value_at_cost))} a Bs ${number(M.bob(last.value_at_cost))}.`);
    }

    async function route() {
        const today = new Date();
        const iso = [today.getFullYear(), String(today.getMonth() + 1).padStart(2, '0'),
            String(today.getDate()).padStart(2, '0')].join('-');
        const day = await window.SD_API.get(
            `${window.SD_CONFIG.API_URL}/v1/commercial/statistics/day/${iso}`).catch(() => null);
        if (!day || day.stock_available_value == null) {
            paint('route', '—', 'Hoy no hay stock cargado para la calle.');
            return;
        }
        paint('route', `Bs ${number(day.stock_available_value)}`,
            `disponible hoy en la calle, con ${number(day.sellers_on_route)} vendedores en ruta.`);
    }

    async function load() {
        O.loading(TITLES);
        const datasetId = await window.SD_API.ensureDataset();
        if (!datasetId) {
            qs('#areaTiles').hidden = true;
            qs('#areaEmpty').hidden = false;
            return;
        }
        const id = encodeURIComponent(datasetId);
        const query = A.periodQuery(A.readStoredPeriod());
        O.analysis('stock', `${BASE}/stock/${id}${query}`, stock, () => failed('stock'));
        O.analysis('stockHistory', `${BASE}/stock-history/${id}${query}`, history,
            () => failed('stockHistory'));
        route();
    }

    load();
});
