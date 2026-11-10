/**
 * Facilities: the client's sites, with their general data, where they are
 * and the size of their plan. Opening one goes to its plan.
 */
import { listFacilities, listWarehouses, resetSample, saveFacility } from '../store.js';
import { escapeHtml, icon, metres, notify, numberOf, selection } from '../ui.js';

const FIELDS = [
    ['code', 'Código', 'text'], ['name', 'Nombre', 'text'], ['city', 'Ciudad', 'text'],
    ['address', 'Dirección', 'text'], ['phone', 'Teléfono', 'text'], ['email', 'Correo', 'email'],
    ['lat', 'Latitud', 'number'], ['lng', 'Longitud', 'number'],
    ['plan_width_m', 'Ancho del plano (m)', 'number'], ['plan_length_m', 'Largo del plano (m)', 'number']
];

function formMarkup(facility) {
    const value = (key) => escapeHtml(facility ? facility[key] ?? '' : '');
    return `
        <form class="card" id="facilityForm" novalidate>
            <h3>${facility ? 'Corregir la instalación' : 'Nueva instalación'}</h3>
            <div class="field-row">${FIELDS.map(([key, label, type]) => `
                <label class="field"><span>${label}</span>
                    <input type="${type}" name="${key}" value="${value(key)}"
                           ${type === 'number' ? 'step="any"' : ''}
                           ${['code', 'name', 'plan_width_m', 'plan_length_m'].includes(key) ? 'required' : ''}></label>`).join('')}
            </div>
            <div class="form-actions">
                <button type="button" class="btn btn-cancel" data-btn-icon="close" id="facilityCancel">Cancelar</button>
                <button type="submit" class="btn btn-save" data-btn-icon="check">Guardar</button>
            </div>
        </form>`;
}

export async function mountFacilities(host, { go }) {
    const facilities = await listFacilities();
    const counts = await Promise.all(facilities.map((one) => listWarehouses(one.id)));
    host.innerHTML = `
        <header class="sd-page-head"><div>
            <h1>Instalaciones</h1>
            <p>Cada instalación tiene su plano con sus almacenes. Cada usuario trabaja en una instalación.</p>
        </div></header>
        <section class="card">
            <div class="form-actions">
                <button type="button" class="btn btn-primary" data-btn-icon="plus" id="facilityNew">Nueva instalación</button>
                <button type="button" class="btn btn-ghost" data-btn-icon="refresh" id="facilityReset">Restaurar el ejemplo</button>
            </div>
            <div class="table-wrapper"><table class="data-table">
                <thead><tr><th>Código</th><th>Nombre</th><th>Ciudad</th><th class="numeric">Almacenes</th>
                    <th class="numeric">Plano</th><th></th></tr></thead>
                <tbody>${facilities.map((one, index) => `
                    <tr data-id="${escapeHtml(one.id)}">
                        <td><strong>${escapeHtml(one.code)}</strong></td>
                        <td>${escapeHtml(one.name)}${one.is_sample ? ' <span class="badge badge-info">ejemplo</span>' : ''}</td>
                        <td>${escapeHtml(one.city)}</td>
                        <td class="numeric">${counts[index].length}</td>
                        <td class="numeric">${metres(one.plan_width_m)} × ${metres(one.plan_length_m)}</td>
                        <td class="row-actions">
                            <button type="button" class="btn-icon open" data-tip="Abrir el plano" aria-label="Abrir el plano">${icon('play')}</button>
                            <button type="button" class="btn-icon edit" data-tip="Corregir" aria-label="Corregir">${icon('edit')}</button>
                        </td>
                    </tr>`).join('') || '<tr class="empty-row"><td colspan="6">Todavía no hay instalaciones.</td></tr>'}
                </tbody>
            </table></div>
        </section>
        <div id="facilityEditor"></div>`;

    const editor = host.querySelector('#facilityEditor');
    const openEditor = (facility) => {
        editor.innerHTML = formMarkup(facility);
        const form = editor.querySelector('#facilityForm');
        form.querySelector('#facilityCancel').addEventListener('click', () => { editor.innerHTML = ''; });
        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            if (!form.reportValidity()) return;
            const data = Object.fromEntries(FIELDS.map(([key, , type]) =>
                [key, type === 'number' ? numberOf(form, key, null) : form.elements[key].value.trim()]));
            await saveFacility({ ...(facility || {}), ...data });
            notify('Instalación guardada.', 'success');
            await mountFacilities(host, { go });
        });
        form.scrollIntoView({ behavior: 'smooth', block: 'start' });
    };

    host.querySelector('#facilityNew').addEventListener('click', () => openEditor(null));
    host.querySelector('#facilityReset').addEventListener('click', async () => {
        await resetSample();
        notify('Se restauró la instalación de ejemplo.', 'success');
        await mountFacilities(host, { go });
    });
    host.querySelector('tbody').addEventListener('click', (event) => {
        const row = event.target.closest('tr[data-id]');
        if (!row) return;
        const facility = facilities.find((one) => one.id === row.dataset.id);
        if (event.target.closest('.edit')) openEditor(facility);
        if (event.target.closest('.open')) {
            selection.facility = facility.id;
            go('plan');
        }
    });
}
