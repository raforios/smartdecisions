'use strict';

/**
 * Rutas — "Comparación": one plan against every execution of it in a period.
 * The table scores each run (planned stops, stops visited, points reported);
 * the map draws the plan and the chosen run on top of each other.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.isAuthenticated()) return;
    const { qs, setButtonBusy } = window.SD_UI;
    const T = window.SD_TRACK;

    const compareMap = T.createMap('compareMap');
    const state = { plans: [], full: null, scores: [] };

    qs('#compareFrom').value = T.todayIso(-30);
    qs('#compareTo').value = T.todayIso();

    document.addEventListener('sd:plans-loaded', (event) => fillPlans(event.detail));

    async function ensurePlans() {
        if (state.plans.length) return;
        try {
            fillPlans(await T.planned.list());
        } catch (error) {
            note(T.errorText(error, 'No se pudieron cargar los planes.'), 'error');
        }
    }

    function fillPlans(plans) {
        state.plans = plans;
        const select = qs('#comparePlan');
        const current = select.value;
        select.innerHTML = '';
        plans.forEach((plan) => {
            const option = document.createElement('option');
            option.value = plan.id;
            option.textContent = `${plan.route_code} · ${plan.route_name}` +
                (plan.seller ? ` · ${plan.seller}` : '');
            select.appendChild(option);
        });
        if (current) select.value = current;
    }

    function filters() {
        const params = {};
        if (qs('#compareFrom').value) params.date_from = qs('#compareFrom').value;
        if (qs('#compareTo').value) params.date_to = qs('#compareTo').value;
        if (qs('#compareSeller').value.trim()) params.seller = qs('#compareSeller').value.trim();
        return params;
    }

    async function compare() {
        const planId = qs('#comparePlan').value;
        if (!planId) { note('Elige un plan.', 'error'); return; }
        const done = setButtonBusy(qs('#compareButton'), 'Comparando…');
        note('Consultando ejecuciones…');
        try {
            const [scored, full] = await Promise.all([
                T.stats.comparisons(planId, filters()),
                T.stats.full(planId, filters())
            ]);
            state.scores = scored.comparisons;
            state.full = full;
            paintScores();
            drawRun(full.executed_routes[0] || null);
            paintSummary();
            note(state.scores.length ? '' : 'Ninguna ejecución de este plan en el período.');
        } catch (error) {
            note(T.errorText(error, 'No se pudo comparar.'), 'error');
        } finally {
            done();
        }
    }

    function paintSummary() {
        const scores = state.scores;
        const average = scores.length
            ? scores.reduce((sum, score) => sum + score.match_percentage, 0) / scores.length : 0;
        const sales = (state.full.executed_routes || []).reduce((sum, route) =>
            sum + route.points.filter((point) => point.outcome === 'VENTA').length, 0);
        qs('#compareSummary').innerHTML =
            metric('Paradas planificadas', String(state.full.planned_route.points.length)) +
            metric('Ejecuciones', String(scores.length)) +
            metric('Cumplimiento medio', `${T.formatDecimal(average)} %`) +
            metric('Visitas con venta', String(sales));
        qs('#compareSummary').hidden = false;
    }

    function paintScores() {
        const tbody = qs('#compareTable tbody');
        tbody.innerHTML = '';
        const runs = Object.fromEntries((state.full.executed_routes || []).map((run) => [run.id, run]));
        state.scores.forEach((score) => {
            const run = runs[score.executed_route_id];
            const row = document.createElement('tr');
            row.dataset.id = score.executed_route_id;
            row.innerHTML =
                `<td>${T.escapeHtml(run ? T.formatStamp(run.start_time) : score.executed_route_id)}</td>` +
                `<td>${T.escapeHtml(score.seller)}</td>` +
                `<td class="numeric">${score.planned_points_count}</td>` +
                `<td class="numeric">${score.matched_points_count}</td>` +
                `<td class="numeric">${score.points_visited_count}</td>` +
                `<td class="numeric"><strong>${T.formatDecimal(score.match_percentage)} %</strong></td>` +
                `<td class="numeric"><button class="btn btn-ghost btn-small" data-action="map">Ver</button></td>`;
            tbody.appendChild(row);
        });
    }

    qs('#compareTable').addEventListener('click', (event) => {
        const button = event.target.closest('[data-action="map"]');
        if (!button) return;
        const id = button.closest('tr').dataset.id;
        drawRun((state.full.executed_routes || []).find((run) => run.id === id) || null);
    });

    /** The plan in one colour, the run's visits on top; breadcrumbs muted. */
    function drawRun(run) {
        compareMap.clear();
        const points = [];
        const plan = state.full.planned_route;
        plan.points.forEach((stop) => {
            points.push([stop.latitude, stop.longitude]);
            compareMap.marker(stop.latitude, stop.longitude, stop.secuencial, T.PIN_COLORS.plan,
                `<strong>Plan ${stop.secuencial}. ${T.escapeHtml(stop.point_name)}</strong>`);
        });
        if (points.length > 1) compareMap.line(points, T.PIN_COLORS.plan, true);
        if (run) {
            const path = [];
            run.points.forEach((point, index) => {
                path.push([point.latitude, point.longitude]);
                const isVisit = Boolean(point.client_id);
                compareMap.marker(point.latitude, point.longitude,
                    isVisit ? index + 1 : '·',
                    point.outcome === 'VENTA' ? T.PIN_COLORS.sale : T.PIN_COLORS.point,
                    `<strong>${T.escapeHtml(T.formatStamp(point.timestamp))}</strong><br>` +
                    `${T.escapeHtml(point.client_id || 'posición')}` +
                    (point.outcome ? ` · ${T.escapeHtml(T.OUTCOME_LABELS[point.outcome] || point.outcome)}` : '') +
                    (point.items && point.items.length
                        ? `<br>${point.items.map((item) => `${T.escapeHtml(item.sku)} × ${T.formatQuantity(item.quantity)}`).join(', ')}`
                        : ''));
            });
            if (path.length > 1) compareMap.line(path, T.PIN_COLORS.seller, false);
            points.push(...path);
        }
        compareMap.refresh();
        compareMap.fit(points);
    }

    function metric(label, value) {
        return `<div class="metric"><p class="metric-label">${T.escapeHtml(label)}</p>` +
               `<p class="metric-value">${T.escapeHtml(value)}</p></div>`;
    }
    function note(text, kind) { T.note(qs('#compareNote'), text, kind); }

    qs('#compareButton').addEventListener('click', compare);

    T.onShow('compare', () => { compareMap.refresh(); ensurePlans(); });
});
