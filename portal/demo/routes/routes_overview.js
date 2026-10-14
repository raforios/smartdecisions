'use strict';

/**
 * Comercial › Rutas — the area's summary, shown when no option is open. The
 * options open from the side menu (`#planner`, `#live`…); this page only
 * decides whether the summary or an option is on screen.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.isAuthenticated()) return;
    const O = window.SD_OVERVIEW;
    const { number } = O;
    const qs = (selector) => document.querySelector(selector);

    const TITLES = { live: 'En vivo', compare: 'Comparación', planner: 'Histórico',
        plans: 'Planes', optimize: 'Optimizar' };
    const paint = (name, ...rest) => O.paint(name, TITLES[name], ...rest);
    const isoDay = (offset) => {
        const day = new Date(Date.now() + offset * 86400000);
        return [day.getFullYear(), String(day.getMonth() + 1).padStart(2, '0'),
            String(day.getDate()).padStart(2, '0')].join('-');
    };

    /** The summary without an option in the address; the option otherwise. */
    function place() {
        const summary = !location.hash;
        qs('#routesTiles').hidden = !summary;
        if (summary) {
            document.querySelectorAll('.routes-section').forEach((panel) => { panel.hidden = true; });
        }
    }

    async function load() {
        O.loading(TITLES);
        paint('planner', 'Lo que ya se hizo', 'Las rutas recorridas sobre el mapa. Desde aquí se repite una ruta.');
        paint('plans', 'Lo que viene', 'De hoy en adelante: impórtalos, infiérelos, asígnalos y actívalos.');
        paint('optimize', 'El orden más corto', 'La ruta que ya tienes contra el orden que la acorta, con el ahorro.');
        const day = (offset) => window.SD_API.get(`${window.SD_CONFIG.OPTIMIZATION_URL}` +
            `/v1/optimization/statistics/day/${isoDay(offset)}`).catch(() => null);
        const [today, yesterday] = await Promise.all([day(0), day(-1)]);
        O.tile('live').innerHTML =
            `<p class="sd-hero-label">${TITLES.live}: el día de hoy</p>` +
            `<p class="sd-hero-value">${number(today && today.sellers_on_route)} en la calle</p>` +
            `<div class="sd-hero-other"><span>Rutas iniciadas<b>${number(today && today.routes_started)}</b></span>` +
            `<span>Rutas cerradas<b>${number(today && today.routes_closed)}</b></span>` +
            `<span>Km recorridos<b>${number(today && today.distance_km, 1)}</b></span>` +
            `<span>Venta en la calle<b>Bs ${number(today && today.sales_amount)}</b></span></div>`;
        paint('compare', !yesterday || yesterday.visit_compliance == null ? 'Sin plan ayer'
            : `${number(yesterday.visit_compliance, 1)} %`,
            'de las paradas planificadas de ayer se visitaron.');
    }

    window.addEventListener('hashchange', place);
    place();
    load();
});
