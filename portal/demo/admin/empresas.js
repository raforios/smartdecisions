'use strict';

/**
 * Administración › Empresas — the customers of the platform (ADMIN only).
 *
 * A company is the `client` its users share and every service keys its data
 * by, so its name never changes; its NIT and whether it is active do. One
 * with users is not removed, it is deactivated (AUTH refuses it with
 * COMPANY_HAS_USERS).
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.isAuthenticated() || !window.SD_CONFIG.API_URL) return;
    const { qs, toast, setButtonBusy } = window.SD_UI;
    const icon = window.SD_ICONS.svg;
    const API = window.SD_API;
    const BASE = `${window.SD_CONFIG.API_URL}/v1/auth/companies`;
    const escape = (text) => String(text == null ? '' : text)
        .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;');

    // AUTH answers with codes; the words live here.
    const ERRORS = {
        COMPANY_NOT_FOUND: 'Esa empresa ya no existe.',
        DUPLICATE_COMPANY: 'Ya hay una empresa con ese nombre.',
        COMPANY_HAS_USERS: 'La empresa tiene usuarios: no se elimina, se deja inactiva.',
        COMPANY_INACTIVE: 'La empresa está inactiva.'
    };
    const failure = (error, fallback) => {
        const code = error && (error.code || error.message);
        if (ERRORS[code]) return ERRORS[code];
        if (error && error.status === 422) return 'Revisa los datos: el nombre de 3 a 50 letras y el NIT sólo con números.';
        return fallback;
    };

    const state = { companies: [], editing: null };
    const note = (text, kind) => {
        const element = qs('#companiesNote');
        element.className = `form-note${kind ? ` ${kind}` : ''}`;
        element.textContent = text || '';
    };

    async function load() {
        try {
            state.companies = await API.get(BASE);
            paint();
            note('');
            qs('#companyNew').disabled = false;
        } catch (error) {
            note(failure(error, 'No se pudieron leer las empresas.'), 'error');
        }
    }

    function paint() {
        const text = qs('#companiesSearch').value.trim().toLowerCase();
        const rows = state.companies.filter((company) => !text ||
            `${company.name} ${company.tax_id || ''}`.toLowerCase().includes(text));
        qs('#companiesCount').textContent = `${rows.length} de ${state.companies.length} empresas.`;
        qs('#companiesTable tbody').innerHTML = rows.map((company) => `
            <tr>
                <td><b>${escape(company.name)}</b></td>
                <td>${escape(company.tax_id || '—')}</td>
                <td class="numeric">${company.users}</td>
                <td><span class="sd-status ${company.active ? 'is-on' : 'is-off'}">
                    ${company.active ? 'Activa' : 'Inactiva'}</span></td>
                <td class="row-actions">
                    <button type="button" class="btn-icon" data-tip="Editar" aria-label="Editar"
                            data-edit="${escape(company.name)}">${icon('edit')}</button>
                    ${company.users ? '' : `<button type="button" class="btn-icon is-delete" data-tip="Eliminar"
                            aria-label="Eliminar" data-delete="${escape(company.name)}">${icon('trash')}</button>`}
                </td>
            </tr>`).join('');
    }

    function openForm(company) {
        state.editing = company || null;
        const creating = !company;
        qs('#companyFormTitle').textContent = creating ? 'Nueva empresa' : `Editar ${company.name}`;
        qs('#companyNameField').hidden = !creating;
        qs('#companyActiveField').hidden = creating;
        qs('#companyName').value = '';
        qs('#companyTaxId').value = creating ? '' : (company.tax_id || '');
        qs('#companyActive').value = creating ? 'true' : String(company.active);
        qs('#companyForm').hidden = false;
        qs(creating ? '#companyName' : '#companyTaxId').focus();
    }

    function closeForm() {
        state.editing = null;
        qs('#companyForm').hidden = true;
        qs('#companiesTable').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    async function save(button) {
        const taxId = qs('#companyTaxId').value.trim() || null;
        if (taxId && !/^\d{5,20}$/.test(taxId)) { note('El NIT lleva sólo números, de 5 a 20.', 'error'); return; }
        const done = setButtonBusy(button, 'Guardando…');
        try {
            if (state.editing) {
                await API.patch(`${BASE}/${encodeURIComponent(state.editing.name)}`,
                    { tax_id: taxId, active: qs('#companyActive').value === 'true' });
                toast(`Empresa ${state.editing.name} actualizada.`, 'success');
            } else {
                const name = qs('#companyName').value.trim();
                if (name.length < 3) { note('Escribe el nombre de la empresa.', 'error'); return; }
                await API.post(BASE, { name, tax_id: taxId });
                toast(`Empresa ${name} creada.`, 'success');
            }
            closeForm();
            await load();
        } catch (error) {
            note(failure(error, 'No se pudo guardar la empresa.'), 'error');
        } finally {
            done();
        }
    }

    /** First click asks, the second deletes: no browser dialogs in the portal. */
    async function remove(button) {
        const name = button.dataset.delete;
        if (button.dataset.confirm !== '1') {
            button.dataset.confirm = '1';
            button.dataset.tip = 'Confirmar eliminación';
            button.classList.add('is-danger');
            note(`Eliminar ${name} no se puede deshacer.`);
            return;
        }
        const done = setButtonBusy(button);
        try {
            await API.del(`${BASE}/${encodeURIComponent(name)}`);
            toast(`Empresa ${name} eliminada.`, 'success');
            note('');
            await load();
        } catch (error) {
            note(failure(error, 'No se pudo eliminar la empresa.'), 'error');
            done();
        }
    }

    // The NIT only takes numbers, refused as typed (like the account codes).
    qs('#companyTaxId').addEventListener('beforeinput', (event) => {
        if (event.data && /\D/.test(event.data)) {
            event.preventDefault();
            note('El NIT lleva sólo números.', 'error');
        }
    });
    qs('#companiesSearch').addEventListener('input', paint);
    qs('#companyNew').addEventListener('click', () => { note(''); openForm(null); });
    qs('#companyCancel').addEventListener('click', closeForm);
    qs('#companySave').addEventListener('click', (event) => save(event.currentTarget));
    qs('#companiesTable').addEventListener('click', (event) => {
        const edit = event.target.closest('[data-edit]');
        if (edit) {
            note('');
            openForm(state.companies.find((company) => company.name === edit.dataset.edit));
            return;
        }
        const del = event.target.closest('[data-delete]');
        if (del) remove(del);
    });

    load();
});
