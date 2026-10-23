'use strict';

/**
 * Prompts de la IA — the expert each view is explained by.
 *
 * AI keeps every version: editing stores the next version and retires the one
 * in force, and turning an old version on is the rollback. Prompts per company
 * (Rafael, 21-oct): the ADMIN writes the general ones, the defaults of every
 * company, sees every company's and may delete any; a manager sees the general
 * ones and writes their company's, starting from a general one. AI takes the
 * company from the token: the screen never sends it.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.isAuthenticated() || !window.SD_CONFIG.API_URL) return;
    const { qs, toast, setButtonBusy } = window.SD_UI;
    const icon = window.SD_ICONS.svg;
    const BASE = `${window.SD_CONFIG.API_URL}/v1/ai/roles`;
    const admin = window.SD_SHELL && window.SD_SHELL.role === 'ADMIN';
    const GENERAL = 'General';
    const companyOf = (role) => role.client || GENERAL;

    // The service names each view with a code; the screen with its name.
    const VIEW_LABELS = {
        commercial_summary: 'Resumen Comercial',
        volume_source: 'Fuente de volumen',
        objectives: 'Cumplimiento de objetivos',
        receivables: 'Cuentas por cobrar',
        stock: 'Stock del día',
        opportunities: 'Oportunidades de venta',
        segmentation: 'Segmentación de clientes',
        sales_forecast: 'Pronóstico de demanda',
        portfolio: 'Salud de cartera',
        fx_effect: 'Efecto del tipo de cambio',
        route_plan: 'Rutas · Histórico',
        route_plans: 'Rutas · Planes',
        route_live: 'Rutas · En vivo',
        route_optimize: 'Rutas · Optimizar',
        route_compare: 'Rutas · Comparación',
        minerals_forecast: 'Minerales · proyección',
        rate_forecast: 'Tipo de cambio · proyección',
        sale_scenario: 'Minerales · escenario de venta',
        finance_summary: 'Análisis Financiero · Resumen',
        finance_income: 'Análisis Financiero · Estado de Resultados',
        finance_balance: 'Análisis Financiero · Balance General',
        finance_taxes: 'Análisis Financiero · Impuestos',
        finance_projection: 'Análisis Financiero · Proyección',
        finance_business_model: 'Análisis Financiero · Modelo de negocio'
    };
    const viewLabel = (code) => VIEW_LABELS[code] || code;
    const escape = (text) => String(text == null ? '' : text)
        .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;');

    const state = { roles: [] };
    const note = (text, kind) => {
        const element = qs('#promptsNote');
        element.className = `form-note${kind ? ` ${kind}` : ''}`;
        element.textContent = text || '';
    };

    async function load() {
        try {
            const data = await window.SD_API.get(BASE);
            state.roles = (data.roles || []).slice().sort((left, right) =>
                viewLabel(left.view).localeCompare(viewLabel(right.view)) ||
                right.version - left.version);
            if (admin) fillCompanies();
            paint();
            note(state.roles.length ? '' : 'Todavía no hay prompts configurados.');
        } catch (error) {
            note((error && error.message) || 'No se pudieron leer los prompts.', 'error');
        }
    }

    /** The ADMIN's filter: General and every company that has its own prompts. */
    function fillCompanies() {
        const select = qs('#promptsCompany');
        const chosen = select.value;
        const companies = [...new Set(state.roles.map((role) => role.client).filter(Boolean))].sort();
        select.innerHTML = '<option value="">Todas</option>' +
            `<option value="${GENERAL}">${GENERAL}</option>` +
            companies.map((name) => `<option value="${escape(name)}">${escape(name)}</option>`).join('');
        select.value = chosen;
    }

    /**
     * What each row offers. Own prompts (the ADMIN's general ones, a manager's
     * company ones) are edited and switched; a manager starts theirs from a
     * general one; the ADMIN deletes any.
     */
    function actions(role) {
        const own = admin ? !role.client : Boolean(role.client);
        const key = `data-view="${role.view}" data-version="${role.version}"`;
        const edit = own || !admin ? `<button type="button" class="btn-icon" ${key}
                data-action="edit" data-tip="${own ? 'Editar' : 'Crear el de mi empresa a partir de este'}"
                aria-label="${own ? 'Editar' : 'Crear el de mi empresa'}">${icon(own ? 'edit' : 'plus')}</button>` : '';
        const toggle = own ? `<button type="button" class="btn-icon${role.active ? ' is-on' : ''}" ${key}
                data-action="toggle" data-active="${role.active}"
                data-tip="${role.active ? 'Desactivar' : 'Activar'}"
                aria-label="${role.active ? 'Desactivar' : 'Activar'}">${icon('power')}</button>` : '';
        const remove = admin ? `<button type="button" class="btn-icon" ${key} data-action="delete"
                data-tip="Eliminar" aria-label="Eliminar">${icon('trash')}</button>` : '';
        return edit + toggle + remove;
    }

    function paint() {
        const company = admin ? qs('#promptsCompany').value : '';
        const rows = state.roles.filter((role) => !company || companyOf(role) === company);
        qs('#promptsTable tbody').innerHTML = rows.map((role) => `
            <tr>
                <td>${escape(viewLabel(role.view))}</td>
                <td>${escape(companyOf(role))}</td>
                <td class="numeric">${role.version}</td>
                <td>${escape(role.role)}</td>
                <td>${role.active ? 'En uso' : 'Inactivo'}</td>
                <td class="row-actions">${actions(role)}</td>
            </tr>`).join('');
    }

    async function edit(view, version) {
        try {
            const role = await window.SD_API.get(`${BASE}/${view}/${version}`);
            const form = qs('#promptForm');
            form.hidden = false;
            // A manager opening a general prompt starts their company's from it.
            const starting = !admin && !role.client;
            qs('#promptView').textContent = starting
                ? `${viewLabel(view)} — el de tu empresa, a partir de la versión general ${version}`
                : `${viewLabel(view)} — versión ${version}`;
            form.dataset.view = view;
            form.dataset.model = role.model_id;
            qs('#promptRole').value = role.role;
            qs('#promptInstructions').value = role.instructions;
            qs('#promptRules').value = (role.rules || []).join('\n');
            qs('#promptMaxTokens').value = role.max_tokens;
            form.scrollIntoView({ behavior: 'smooth', block: 'start' });
        } catch (error) {
            note((error && error.message) || 'No se pudo leer el prompt.', 'error');
        }
    }

    async function saveVersion(button) {
        const form = qs('#promptForm');
        const view = form.dataset.view;
        const done = setButtonBusy(button, 'Guardando…');
        try {
            // An edit is a new version, never a rewrite of one; AI numbers it
            // across every company and takes the company from the token.
            const saved = await window.SD_API.post(BASE, {
                view,
                version: 1,
                role: qs('#promptRole').value.trim(),
                instructions: qs('#promptInstructions').value.trim(),
                rules: qs('#promptRules').value.split('\n').map((rule) => rule.trim())
                    .filter(Boolean),
                max_tokens: Number(qs('#promptMaxTokens').value),
                model_id: form.dataset.model,
                active: true
            });
            form.hidden = true;
            // A company's version retires only the company's earlier one: the
            // general one stays in force for every other company.
            toast(saved.client
                ? `Guardado como versión ${saved.version} de tu empresa; desde ahora la IA usa ésta.`
                : `Guardado como versión ${saved.version}; la anterior quedó inactiva.`, 'success');
            await load();
        } catch (error) {
            note((error && error.message) || 'No se pudo guardar el prompt.', 'error');
        } finally {
            done();
        }
    }

    async function toggle(view, version, active, button) {
        const done = setButtonBusy(button, '…');
        try {
            await window.SD_API.patch(`${BASE}/${view}/${version}/active`, { active: !active });
            toast(active ? 'Prompt desactivado.' : 'Prompt activado; el anterior quedó inactivo.',
                  'success');
            await load();
        } catch (error) {
            note((error && error.message) || 'No se pudo cambiar el prompt.', 'error');
        } finally {
            done();
        }
    }

    /** First click asks, the second deletes: no browser dialogs in the portal. */
    async function remove(view, version, button) {
        if (button.dataset.confirm !== '1') {
            button.dataset.confirm = '1';
            button.dataset.tip = 'Confirmar eliminación';
            button.classList.add('is-danger');
            note(`Eliminar la versión ${version} de ${viewLabel(view)} no se puede deshacer.`);
            return;
        }
        const done = setButtonBusy(button, '…');
        try {
            await window.SD_API.del(`${BASE}/${view}/${version}`);
            toast(`Versión ${version} de ${viewLabel(view)} eliminada.`, 'success');
            note('');
            await load();
        } catch (error) {
            note((error && error.message) || 'No se pudo eliminar el prompt.', 'error');
            done();
        }
    }

    qs('#promptsTable').addEventListener('click', (event) => {
        const button = event.target.closest('button[data-action]');
        if (!button) return;
        const { view, action } = button.dataset;
        const version = Number(button.dataset.version);
        if (action === 'edit') edit(view, version);
        if (action === 'toggle') toggle(view, version, button.dataset.active === 'true', button);
        if (action === 'delete') remove(view, version, button);
    });
    if (admin) {
        qs('#promptsFilters').hidden = false;
        qs('#promptsCompany').addEventListener('change', paint);
    } else {
        qs('#promptsSubtitle').textContent = 'El experto con que la IA explica cada pantalla. ' +
            'Los generales valen para todas las empresas; los de tu empresa, sólo para la tuya.';
        qs('#promptsHint').textContent = 'Para ajustar uno, créalo para tu empresa a partir del ' +
            'general: desde entonces la IA usa el tuyo. Si lo desactivas, vuelve a usar el general.';
    }
    qs('#promptSave').addEventListener('click', (event) => saveVersion(event.currentTarget));
    // Cancel closes the form unsaved and takes the reader back to the list.
    qs('#promptCancel').addEventListener('click', () => {
        qs('#promptForm').hidden = true;
        qs('#promptsTable').scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
    qs('#promptsSection').hidden = false;
    load();
});
