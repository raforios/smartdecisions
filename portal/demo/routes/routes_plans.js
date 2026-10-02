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
        // This screen is what is COMING. A plan carries the day it is meant to
        // be run, so asking from today on is what keeps yesterday out of it —
        // yesterday belongs to Histórico. A plan with no date is a reusable
        // template and answers to no window, so it stays.
        const filters = {};
        if (status) filters.route_status = status;
        if (qs('#plansOnlyUpcoming').checked) filters.date_from = T.todayIso();
        state.plans = [];
        note('#plansNote', 'Cargando planes…');
        try {
            state.plans = await T.planned.filter(filters);
            paintPlans();
            note('#plansNote', state.plans.length ? '' :
                'No hay planes para este período. Quita el filtro para ver los anteriores.');
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
        fillSellerSelect(plan);
    }

    // ---------- assignment ----------
    // A plan with no seller is offered to nobody's phone: assigning it is what
    // puts it in front of one seller, and what the comparison measures them by.
    let sellerNames = null;
    async function fillSellerSelect(plan) {
        const select = qs('#planSellerSelect');
        T.note(qs('#planSellerNote'), '');
        if (sellerNames === null) {
            try {
                sellerNames = ((await T.sellers.list()).sellers || []).map((seller) => seller.id);
            } catch (error) {
                sellerNames = [];
                T.note(qs('#planSellerNote'),
                       T.errorText(error, 'No se pudo leer la lista de vendedores.'), 'error');
            }
        }
        const names = plan.seller && !sellerNames.includes(plan.seller)
            ? [plan.seller, ...sellerNames] : sellerNames;
        select.innerHTML = '<option value="">— Sin asignar —</option>' + names
            .map((name) => `<option value="${T.escapeHtml(name)}">${T.escapeHtml(name)}</option>`)
            .join('');
        select.value = plan.seller || '';
    }

    qs('#planSellerButton').addEventListener('click', async () => {
        if (!state.selected) return;
        const seller = qs('#planSellerSelect').value || null;
        const done = setButtonBusy(qs('#planSellerButton'), 'Asignando…');
        try {
            const plan = await T.planned.update(state.selected.id, { seller });
            toast(seller ? `Plan asignado a ${seller}.` : 'Plan sin vendedor.', 'success');
            await loadPlans();
            showPlan(state.plans.find((item) => item.id === plan.id) || plan);
        } catch (error) {
            T.note(qs('#planSellerNote'), T.errorText(error, 'No se pudo asignar.'), 'error');
        } finally {
            done();
        }
    });
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
    qs('#plansOnlyUpcoming').addEventListener('change', loadPlans);

    // ---------- template ----------
    qs('#planTemplateButton').addEventListener('click', () => {
        // Headers in Spanish, like every template of the product; the mapper
        // on the service turns them into the contract's own names.
        const headers = ['Codigo Ruta', 'Nombre Ruta', 'Fecha', 'Vendedor',
                         'Descripcion', 'Cliente', 'Secuencia', 'Latitud',
                         'Longitud', 'Referencia', 'Cliente ID'];
        const example = ['R-SUR', 'Zona Sur', T.todayIso(), 'Ana Quispe',
                         'Ruta del lunes', 'Tienda Doña Rosa', '1', '-16.5435',
                         '-68.0713', 'Frente a la plaza', 'PDV-001'];
        const csv = `${headers.join(',')}\n${example.join(',')}\n`;
        const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = 'plantilla_rutas.csv';
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        URL.revokeObjectURL(url);
        note('#bulkPlanNote', 'Plantilla descargada.', 'success');
    });

    function note(selector, text, kind) { T.note(qs(selector), text, kind); }

    let loaded = false;
    T.onShow('plans', () => {
        planMap.refresh();
        if (!loaded) { loaded = true; loadPlans(); }
    });
});
