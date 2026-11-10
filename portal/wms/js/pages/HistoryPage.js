/**
 * The layout's history: every saved version of a plan (the facility's, or a
 * warehouse's), what changed in it one by one, and the plan as it was.
 */
import { PlanEditor } from '../plan.js';
import { elementTypes, listFacilities, listWarehouses, versions } from '../store.js';
import { escapeHtml, icon, metres, selection, stamp } from '../ui.js';

const ACTIONS = {
    CREATE: 'Agregado', MOVE: 'Movido', RESIZE: 'Medidas', RECODE: 'Código nuevo',
    UPDATE: 'Corregido', DELETE: 'Quitado'
};
const ENTITIES = { WAREHOUSE: 'Almacén', AISLE: 'Pasillo', ELEMENT: 'Elemento' };

export async function mountHistory(host) {
    const facilities = await listFacilities();
    const facility = facilities.find((one) => one.id === selection.facility) || facilities[0];
    if (!facility) {
        host.innerHTML = '<div class="card"><p>Primero crea una instalación.</p></div>';
        return;
    }
    const warehouses = await listWarehouses(facility.id);
    const types = await elementTypes();
    const plans = [{ scope: 'FACILITY', id: facility.id, label: `Plano de ${facility.name}`,
                     width: facility.plan_width_m, length: facility.plan_length_m },
                   ...warehouses.map((one) => ({ scope: 'WAREHOUSE', id: one.id, label: `${one.code} · ${one.name}`,
                                                 width: one.width_m, length: one.length_m }))];

    host.innerHTML = `
        <header class="sd-page-head"><div>
            <h1>Historial del layout</h1>
            <p>Cada vez que se guarda un plano queda una versión completa, con cada cambio por separado.</p>
        </div>
        <label class="field warehouse-pick"><span>Plano</span>
            <select id="planPick">${plans.map((plan, index) => `<option value="${index}">${escapeHtml(plan.label)}</option>`).join('')}</select></label>
        </header>
        <section class="card">
            <div class="table-wrapper"><table class="data-table">
                <thead><tr><th class="numeric">Versión</th><th>Fecha</th><th>Usuario</th><th>Motivo</th>
                    <th class="numeric">Cambios</th><th></th></tr></thead>
                <tbody id="versionRows"></tbody>
            </table></div>
        </section>
        <div id="versionDetail"></div>`;

    const rows = host.querySelector('#versionRows');
    const detail = host.querySelector('#versionDetail');
    let list = [];
    let plan = plans[0];

    async function load() {
        list = await versions(plan.scope, plan.id);
        detail.innerHTML = '';
        rows.innerHTML = list.map((one) => `
            <tr data-id="${escapeHtml(one.id)}">
                <td class="numeric"><strong>${one.version}</strong></td>
                <td>${stamp(one.created_at)}</td>
                <td>${escapeHtml(one.created_by)}</td>
                <td>${escapeHtml(one.note) || '<span class="muted">—</span>'}</td>
                <td class="numeric">${one.changes.length}</td>
                <td class="row-actions"><button type="button" class="btn-icon open" data-tip="Ver la versión"
                    aria-label="Ver la versión">${icon('eye')}</button></td>
            </tr>`).join('') ||
            '<tr class="empty-row"><td colspan="6">Este plano todavía no tiene versiones guardadas.</td></tr>';
    }

    function show(version) {
        detail.innerHTML = `
            <div class="plan-layout">
                <section class="card plan-card">
                    <h3>Versión ${version.version} · ${stamp(version.created_at)}</h3>
                    <div class="plan-host" id="historyPlan"></div>
                </section>
                <aside class="card plan-panel">
                    <p class="panel-label">Cambios (${version.changes.length})</p>
                    <ul class="change-list">${version.changes.map((change) => `
                        <li><span class="badge badge-${change.action === 'DELETE' ? 'danger' : change.action === 'RECODE' ? 'warn' : 'info'}">${ACTIONS[change.action]}</span>
                            ${ENTITIES[change.entity] || change.entity}
                            ${change.old_code && change.new_code && change.old_code !== change.new_code
                                ? `<span class="code">${escapeHtml(change.old_code)}</span> → <span class="code is-new">${escapeHtml(change.new_code)}</span>`
                                : `<span class="code">${escapeHtml(change.new_code || change.old_code || '')}</span>`}</li>`).join('')}
                    </ul>
                </aside>
            </div>`;
        const typeColor = (code) => (types.find((one) => one.code === code) || {}).color || '#6b7590';
        const viewer = new PlanEditor({
            host: detail.querySelector('#historyPlan'), width: plan.width, length: plan.length, readOnly: true,
            look: (item) => {
                if (plan.scope === 'FACILITY') {
                    return { kind: 'warehouse', fill: 'var(--plan-warehouse)', stroke: 'var(--plan-warehouse-line)',
                             label: item.code, sub: item.name, title: `${item.code} · ${metres(item.width_m)} × ${metres(item.length_m)}` };
                }
                return item.entity === 'AISLE'
                    ? { kind: 'aisle', fill: 'var(--plan-aisle)', stroke: 'var(--plan-aisle-line)', label: `Pasillo ${item.number}` }
                    : { kind: 'element', fill: typeColor(item.type), stroke: 'var(--plan-element-line)',
                        label: `${(types.find((one) => one.code === item.type) || {}).code_letter || ''}${item.number}` };
            }
        });
        viewer.setItems(version.snapshot);
        detail.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    host.querySelector('#planPick').addEventListener('change', (event) => {
        plan = plans[Number(event.target.value)];
        load();
    });
    rows.addEventListener('click', (event) => {
        const row = event.target.closest('tr[data-id]');
        if (row && event.target.closest('.open')) show(list.find((one) => one.id === row.dataset.id));
    });
    await load();
}
