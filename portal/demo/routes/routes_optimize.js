'use strict';

/**
 * Rutas — "Optimizar": the route the client already has, against the order
 * that shortens it.
 *
 * The planner builds a week from the sales file. This answers the other
 * question, and the one that gets asked: this route I already have —imported,
 * inferred from a day that was worked, or built by a seller on the street— in
 * what order was it worth doing, and how much would I have saved?
 *
 * Both maps are drawn side by side because a saving nobody can see is not an
 * argument. Nothing is written until the user asks for the optimized plan.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.isAuthenticated()) return;
    const { qs, toast, setButtonBusy } = window.SD_UI;
    const T = window.SD_TRACK;

    const currentMap = T.createMap('currentMap');
    const optimizedMap = T.createMap('optimizedMap');
    const state = { plans: [], study: null, page: 0 };

    (function defaultRepeatDate() {
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        qs('#optimizeRepeatDate').value = tomorrow.toISOString().slice(0, 10);
        qs('#optimizeRepeatDate').min = T.todayIso();
    }());

    /** Every plan of the account can be studied, dated or not. */
    document.addEventListener('sd:plans-loaded', (event) => {
        state.plans = event.detail || [];
        const select = qs('#optimizePlan');
        const chosen = select.value;
        select.innerHTML = state.plans
            .map((plan) => `<option value="${T.escapeHtml(plan.id)}">` +
                `${T.escapeHtml(plan.route_code)}` +
                `${plan.plan_date ? ` · ${T.escapeHtml(plan.plan_date)}` : ''}` +
                ` · ${plan.points.length} paradas</option>`)
            .join('');
        if (chosen) select.value = chosen;
    });

    /**
     * One ordering on one map: the stops numbered in visiting order and the
     * path between them. The street geometry when OSRM answered, straight
     * lines when it did not — the order is right either way.
     */
    function draw(map, shape, colour) {
        map.clear();
        const stops = shape.stops.map((stop) => [stop.latitude, stop.longitude]);
        if (shape.geometry && shape.geometry.length > 1) {
            map.line(shape.geometry.map(([lon, lat]) => [lat, lon]), colour, false);
        } else if (stops.length > 1) {
            map.line(stops, colour, true);
        }
        shape.stops.forEach((stop) => {
            map.marker(stop.latitude, stop.longitude, String(stop.order), colour,
                `<strong>${stop.order}. ${T.escapeHtml(stop.point_name)}</strong>` +
                (stop.order === stop.original_order ? ''
                    : `<br>antes era la ${stop.original_order}`));
        });
        map.refresh();
        map.fit(stops);
    }

    function paintSaving(study) {
        const card = qs('#optimizeSavingCard');
        card.hidden = false;
        const km = (metres) => `${T.formatDecimal(metres / 1000, 1)} km`;
        const min = (seconds) => `${T.formatDecimal(seconds / 60, 0)} min`;
        qs('#optimizeSaving').innerHTML = study.already_optimal
            ? '<div class="day-chip"><span class="day-chip-title">Ya está en el mejor orden</span>' +
              '<span class="day-chip-meta">No hay nada que mejorar: la ruta está bien armada.</span></div>'
            : [
                ['Ahorro', `${km(study.saved_metres)} · ${min(study.saved_seconds)}`],
                ['Es un', `${T.formatDecimal(study.saved_percentage, 1)}% menos`],
                ['Hoy', `${km(study.current.distance_metres)} · ${min(study.current.duration_seconds)}`],
                ['Optimizada', `${km(study.optimized.distance_metres)} · ${min(study.optimized.duration_seconds)}`]
            ].map(([label, value]) =>
                `<div class="day-chip"><span class="day-chip-title">${value}</span>` +
                `<span class="day-chip-meta">${label}</span></div>`).join('');
        qs('#optimizeAcceptButton').disabled = study.already_optimal;
    }

    // Ten rows per page, like every other table in the portal.
    const STOPS_PER_PAGE = 10;

    function paintTable(study, page = 0) {
        const stops = study.optimized.stops;
        const pages = Math.max(1, Math.ceil(stops.length / STOPS_PER_PAGE));
        state.page = Math.min(Math.max(page, 0), pages - 1);
        const from = state.page * STOPS_PER_PAGE;

        const shown = stops.slice(from, from + STOPS_PER_PAGE);
        const tbody = qs('#optimizeTable tbody');
        tbody.innerHTML = shown.map((stop) => {
            const moved = stop.order - stop.original_order;
            const label = moved === 0 ? 'igual'
                : (moved < 0 ? `sube ${Math.abs(moved)}` : `baja ${moved}`);
            return `<tr><td>${stop.order}</td>` +
                `<td>${T.escapeHtml(stop.point_name)}</td>` +
                `<td class="numeric">${stop.original_order}</td>` +
                `<td>${label}</td></tr>`;
        }).join('');
        // Keep the height steady on the last page, so the card does not jump.
        if (stops.length > STOPS_PER_PAGE) {
            tbody.innerHTML += '<tr class="row-filler"><td colspan="4">&nbsp;</td></tr>'
                .repeat(STOPS_PER_PAGE - shown.length);
        }

        qs('#optimizeCount').textContent = stops.length === 1
            ? '1 parada'
            : `${stops.length} paradas`;
        qs('#optimizePage').textContent = `${state.page + 1} / ${pages}`;
        qs('#optimizePrev').disabled = state.page === 0;
        qs('#optimizeNext').disabled = state.page >= pages - 1;
        qs('#optimizePager').hidden = stops.length <= STOPS_PER_PAGE;
    }

    qs('#optimizePrev').addEventListener('click', () => paintTable(state.study, state.page - 1));
    qs('#optimizeNext').addEventListener('click', () => paintTable(state.study, state.page + 1));

    qs('#optimizeButton').addEventListener('click', async () => {
        const planId = qs('#optimizePlan').value;
        if (!planId) { note('#optimizeNote', 'Elige una ruta.', 'error'); return; }
        const done = setButtonBusy(qs('#optimizeButton'), 'Estudiando…');
        try {
            state.study = await T.planned.optimization(planId);
            draw(currentMap, state.study.current, T.PIN_COLORS.point);
            draw(optimizedMap, state.study.optimized, T.PIN_COLORS.sale);
            paintSaving(state.study);
            paintTable(state.study);
            note('#optimizeNote', '');
        } catch (error) {
            qs('#optimizeSavingCard').hidden = true;
            note('#optimizeNote', T.errorText(error, 'No se pudo estudiar la ruta.'), 'error');
        } finally {
            done();
        }
    });

    /** Accepting is a separate act: it creates a NEW plan, dated, and leaves
     *  the studied route exactly as it was. */
    qs('#optimizeAcceptButton').addEventListener('click', async () => {
        if (!state.study) return;
        const when = qs('#optimizeRepeatDate').value;
        if (!when) { note('#optimizeAcceptNote', 'Elige el día.', 'error'); return; }
        const done = setButtonBusy(qs('#optimizeAcceptButton'), 'Creando…');
        try {
            // `optimized` makes the service reorder against the same study,
            // so what is created cannot drift from what was shown here.
            const plan = await T.planned.repeat(state.study.planned_route_id, {
                plan_date: when,
                route_code: `${state.study.route_code}-OPT-${when}`,
                optimized: true
            });
            note('#optimizeAcceptNote',
                 `Creado ${plan.route_code} para el ${when}. Revísalo en Planes.`, 'success');
            toast('Plan optimizado creado.', 'success');
        } catch (error) {
            note('#optimizeAcceptNote',
                 T.errorText(error, 'No se pudo crear el plan.'), 'error');
        } finally {
            done();
        }
    });

    function note(id, text, kind) { T.note(qs(id), text, kind); }

    T.onShow('optimize', () => { currentMap.refresh(); optimizedMap.refresh(); });
});
