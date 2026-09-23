'use strict';

/**
 * Rutas — "En vivo": where each seller last reported from, and today's
 * routes with what they have registered so far. Refreshes on its own while
 * the panel is on screen.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.isAuthenticated()) return;
    const { qs } = window.SD_UI;
    const T = window.SD_TRACK;

    const REFRESH_MS = 30000;
    const liveMap = T.createMap('liveMap');
    const state = { timer: null, visible: false, routes: [] };

    /** Sellers come from the active plans and today's routes; the box stays editable. */
    function knownSellers() {
        const typed = qs('#liveSellers').value.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
        const fromRoutes = state.routes.map((route) => route.seller);
        return Array.from(new Set(typed.concat(fromRoutes)));
    }

    document.addEventListener('sd:plans-loaded', (event) => {
        const box = qs('#liveSellers');
        if (box.value.trim()) return;
        const sellers = Array.from(new Set(
            event.detail.filter((plan) => plan.status === 'ACTIVE' && plan.seller)
                .map((plan) => plan.seller)
        ));
        box.value = sellers.join('\n');
    });

    async function refresh() {
        note('Actualizando…');
        try {
            const today = T.todayIso();
            state.routes = await T.executed.list({ date_from: today, date_to: today });
            paintRoutes();
            const sellers = knownSellers();
            if (!sellers.length) {
                paintLocations([]);
                note('Escribe los vendedores a seguir, o carga sus planes en Planes.');
                return;
            }
            const result = await T.executed.lastLocations(sellers);
            paintLocations(result.locations);
            const missing = sellers.filter((seller) => !result.locations.some((loc) => loc.seller === seller));
            note(missing.length ? `Sin posición reciente: ${missing.join(', ')}.` : '', missing.length ? '' : 'success');
        } catch (error) {
            note(T.errorText(error, 'No se pudo actualizar.'), 'error');
        }
    }

    function paintRoutes() {
        const list = qs('#liveRoutes');
        list.innerHTML = '';
        if (!state.routes.length) {
            list.innerHTML = '<p class="legend-hint">Nadie ha iniciado ruta hoy.</p>';
            return;
        }
        state.routes.forEach((route) => {
            const chip = document.createElement('div');
            chip.className = 'day-chip';
            chip.innerHTML =
                `<span class="day-chip-title">${T.escapeHtml(route.seller)}</span>` +
                `<span class="day-chip-meta">${route.end_time ? 'cerrada' : 'abierta'} · ` +
                `${route.points_count} punto(s) · desde ${T.escapeHtml(T.formatStamp(route.start_time))}</span>`;
            list.appendChild(chip);
        });
    }

    function paintLocations(locations) {
        const tbody = qs('#liveTable tbody');
        tbody.innerHTML = '';
        liveMap.clear();
        const points = [];
        locations.forEach((loc) => {
            const row = document.createElement('tr');
            row.innerHTML =
                `<td>${T.escapeHtml(loc.seller)}</td>` +
                `<td>${T.escapeHtml(T.timeAgo(loc.last_timestamp))}</td>` +
                `<td>${T.escapeHtml(loc.executed_route_id)}</td>` +
                `<td class="numeric">${T.formatDecimal(loc.last_latitude, 6)}</td>` +
                `<td class="numeric">${T.formatDecimal(loc.last_longitude, 6)}</td>`;
            tbody.appendChild(row);
            points.push([loc.last_latitude, loc.last_longitude]);
            liveMap.marker(loc.last_latitude, loc.last_longitude,
                loc.seller.slice(0, 2).toUpperCase(), T.PIN_COLORS.seller,
                `<strong>${T.escapeHtml(loc.seller)}</strong><br>hace ${T.escapeHtml(T.timeAgo(loc.last_timestamp))}`);
        });
        liveMap.refresh();
        liveMap.fit(points);
    }

    function schedule() {
        clearInterval(state.timer);
        state.timer = null;
        if (state.visible && qs('#liveAuto').checked) state.timer = setInterval(refresh, REFRESH_MS);
    }

    qs('#liveRefresh').addEventListener('click', refresh);
    qs('#liveAuto').addEventListener('change', schedule);
    document.getElementById('sectionMenu').addEventListener('click', (event) => {
        const card = event.target.closest('.analysis-card');
        if (card && card.dataset.section !== 'live') { state.visible = false; schedule(); }
    });

    function note(text, kind) { T.note(qs('#liveNote'), text, kind); }

    T.onShow('live', () => {
        state.visible = true;
        liveMap.refresh();
        refresh();
        schedule();
    });
});
