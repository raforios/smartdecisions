'use strict';

/**
 * Rutas — "Planes": the saved plans of the account. Import a CSV another
 * system exported, infer a plan from a seller's day, activate or retire one,
 * delete one still in creation, and see its stops on the map.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.isAuthenticated()) return;
    const { qs, toast, setButtonBusy } = window.SD_UI;
    const T = window.SD_TRACK;

    const state = { plans: [], selected: null };
    const planMap = T.createMap('planMap');

    // ---------- list ----------
    async function loadPlans() {
        const status = qs('#plansStatusFilter').value;
        note('#plansNote', 'Cargando planes…');
        try {
            state.plans = status
                ? await T.planned.filter({ route_status: status })
                : await T.planned.list();
            paintPlans();
            note('#plansNote', state.plans.length ? '' : 'Todavía no hay planes guardados.');
            document.dispatchEvent(new CustomEvent('sd:plans-loaded', { detail: state.plans }));
        } catch (error) {
            note('#plansNote', T.errorText(error, 'No se pudieron cargar los planes.'), 'error');
        }
    }

    function actionsFor(plan) {
        const buttons = [];
        if (plan.status === 'IN CREATION') {
            buttons.push(`<button class="btn btn-primary btn-small" data-action="ACTIVE">Activar</button>`);
            buttons.push(`<button class="btn btn-danger btn-small" data-action="delete">Borrar</button>`);
        } else if (plan.status === 'ACTIVE') {
            buttons.push(`<button class="btn btn-ghost btn-small" data-action="INACTIVE">Desactivar</button>`);
        } else {
            buttons.push(`<button class="btn btn-primary btn-small" data-action="ACTIVE">Reactivar</button>`);
        }
        return buttons.join(' ');
    }

    function paintPlans() {
        const tbody = qs('#plansTable tbody');
        tbody.innerHTML = '';
        state.plans.forEach((plan) => {
            const row = document.createElement('tr');
            row.dataset.id = plan.id;
            if (state.selected && state.selected.id === plan.id) row.classList.add('is-selected');
            row.innerHTML =
                `<td><a href="#" data-action="show">${T.escapeHtml(plan.route_code)}</a></td>` +
                `<td>${T.escapeHtml(plan.route_name)}</td>` +
                `<td>${T.escapeHtml(plan.seller || '—')}</td>` +
                `<td class="numeric">${plan.points.length}</td>` +
                `<td><span class="tier-badge status-${plan.status.replace(' ', '-').toLowerCase()}">` +
                `${T.escapeHtml(T.STATUS_LABELS[plan.status] || plan.status)}</span></td>` +
                `<td>${T.escapeHtml(T.formatStamp(plan.created_at))}</td>` +
                `<td class="numeric">${actionsFor(plan)}</td>`;
            tbody.appendChild(row);
        });
    }

    qs('#plansTable').addEventListener('click', async (event) => {
        const control = event.target.closest('[data-action]');
        if (!control) return;
        event.preventDefault();
        const row = control.closest('tr');
        const plan = state.plans.find((item) => item.id === row.dataset.id);
        if (!plan) return;
        const action = control.dataset.action;
        if (action === 'show') { showPlan(plan); return; }
        try {
            if (action === 'delete') {
                await T.planned.remove(plan.id);
                toast(`Plan ${plan.route_code} borrado.`, 'success');
                if (state.selected && state.selected.id === plan.id) hidePlan();
            } else {
                await T.planned.setStatus(plan.id, action);
                toast(`Plan ${plan.route_code}: ${T.STATUS_LABELS[action]}.`, 'success');
            }
            await loadPlans();
        } catch (error) {
            toast(T.errorText(error, 'No se pudo aplicar el cambio.'), 'error');
        }
    });

    // ---------- detail ----------
    function showPlan(plan) {
        state.selected = plan;
        paintPlans();
        qs('#planDetailTitle').textContent =
            `${plan.route_code} · ${plan.route_name}${plan.seller ? ` · ${plan.seller}` : ''}`;
        const tbody = qs('#planStopsTable tbody');
        tbody.innerHTML = '';
        const points = [];
        planMap.clear();
        plan.points.forEach((stop) => {
            const row = document.createElement('tr');
            row.innerHTML =
                `<td class="numeric">${stop.secuencial}</td>` +
                `<td>${T.escapeHtml(stop.point_name)}</td>` +
                `<td>${T.escapeHtml(stop.client_id || '—')}</td>` +
                `<td class="numeric">${T.formatDecimal(stop.latitude, 6)}</td>` +
                `<td class="numeric">${T.formatDecimal(stop.longitude, 6)}</td>`;
            tbody.appendChild(row);
            points.push([stop.latitude, stop.longitude]);
            planMap.marker(stop.latitude, stop.longitude, stop.secuencial, T.PIN_COLORS.plan,
                `<strong>${stop.secuencial}. ${T.escapeHtml(stop.point_name)}</strong>` +
                (stop.client_id ? `<br>${T.escapeHtml(stop.client_id)}` : ''));
        });
        if (points.length > 1) planMap.line(points, T.PIN_COLORS.seller, true);
        qs('#planDetailCard').hidden = false;
        planMap.refresh();
        planMap.fit(points);
    }
    function hidePlan() {
        state.selected = null;
        qs('#planDetailCard').hidden = true;
    }

    // ---------- import ----------
    qs('#bulkPlanButton').addEventListener('click', async () => {
        const file = qs('#bulkPlanFile').files[0];
        if (!file) { note('#bulkPlanNote', 'Elige un archivo CSV.', 'error'); return; }
        const done = setButtonBusy(qs('#bulkPlanButton'), 'Importando…');
        try {
            const result = await T.planned.bulkUpload(file);
            note('#bulkPlanNote',
                `${result.routes_created} plan(es) con ${result.points_created} paradas. ` +
                'Quedan en creación: revísalos y actívalos.', 'success');
            qs('#bulkPlanFile').value = '';
            await loadPlans();
        } catch (error) {
            note('#bulkPlanNote', T.errorText(error, 'No se pudo importar el archivo.'), 'error');
        } finally {
            done();
        }
    });

    // ---------- infer ----------
    qs('#inferDate').value = T.todayIso();
    qs('#inferButton').addEventListener('click', async () => {
        const seller = qs('#inferSeller').value.trim();
        const date = qs('#inferDate').value;
        if (!seller || !date) { note('#inferNote', 'Indica vendedor y fecha.', 'error'); return; }
        const done = setButtonBusy(qs('#inferButton'), 'Creando…');
        try {
            const plan = await T.planned.infer({ seller, date });
            note('#inferNote', `Plan ${plan.route_code} creado con ${plan.points.length} paradas.`, 'success');
            await loadPlans();
            showPlan(plan);
        } catch (error) {
            note('#inferNote', T.errorText(error, 'No se pudo inferir el plan.'), 'error');
        } finally {
            done();
        }
    });

    qs('#plansRefresh').addEventListener('click', loadPlans);
    qs('#plansStatusFilter').addEventListener('change', loadPlans);

    function note(selector, text, kind) { T.note(qs(selector), text, kind); }

    let loaded = false;
    T.onShow('plans', () => {
        planMap.refresh();
        if (!loaded) { loaded = true; loadPlans(); }
    });
});
