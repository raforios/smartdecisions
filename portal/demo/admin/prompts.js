'use strict';

/**
 * Parámetros — the expert each view is explained by (the AI prompts).
 *
 * AI keeps every version: editing stores the next version and retires the one
 * in force, and turning an old version on is the rollback. Nothing is deleted,
 * so this screen has no delete either.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.isAuthenticated() || !window.SD_CONFIG.API_URL) return;
    const { qs, toast, setButtonBusy } = window.SD_UI;
    const icon = window.SD_ICONS.svg;
    const BASE = `${window.SD_CONFIG.API_URL}/v1/ai/roles`;

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
            paint();
            note(state.roles.length ? '' : 'Todavía no hay prompts configurados.');
        } catch (error) {
            note((error && error.message) || 'No se pudieron leer los prompts.', 'error');
        }
    }

    function paint() {
        qs('#promptsTable tbody').innerHTML = state.roles.map((role) => `
            <tr>
                <td>${escape(viewLabel(role.view))}</td>
                <td class="numeric">${role.version}</td>
                <td>${escape(role.role)}</td>
                <td>${role.active ? 'En uso' : 'Inactivo'}</td>
                <td class="row-actions">
                    <button type="button" class="btn-icon" data-tip="Editar" aria-label="Editar"
                            data-edit="${role.view}" data-version="${role.version}">${icon('edit')}</button>
                    <button type="button" class="btn-icon${role.active ? ' is-on' : ''}"
                            data-tip="${role.active ? 'Desactivar' : 'Activar'}"
                            aria-label="${role.active ? 'Desactivar' : 'Activar'}"
                            data-toggle="${role.view}" data-version="${role.version}"
                            data-active="${role.active}">${icon('power')}</button>
                </td>
            </tr>`).join('');
    }

    async function edit(view, version) {
        try {
            const role = await window.SD_API.get(`${BASE}/${view}/${version}`);
            const form = qs('#promptForm');
            form.hidden = false;
            qs('#promptView').textContent = `${viewLabel(view)} — versión ${version}`;
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
        // An edit is the next version of the view, never a rewrite of one.
        const next = Math.max(0, ...state.roles.filter((role) => role.view === view)
            .map((role) => role.version)) + 1;
        const done = setButtonBusy(button, 'Guardando…');
        try {
            await window.SD_API.post(BASE, {
                view,
                version: next,
                role: qs('#promptRole').value.trim(),
                instructions: qs('#promptInstructions').value.trim(),
                rules: qs('#promptRules').value.split('\n').map((rule) => rule.trim())
                    .filter(Boolean),
                max_tokens: Number(qs('#promptMaxTokens').value),
                model_id: form.dataset.model,
                active: true
            });
            form.hidden = true;
            toast(`Guardado como versión ${next}; la anterior quedó inactiva.`, 'success');
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

    qs('#promptsTable').addEventListener('click', (event) => {
        const button = event.target.closest('button');
        if (!button) return;
        const version = Number(button.dataset.version);
        if (button.dataset.edit) edit(button.dataset.edit, version);
        if (button.dataset.toggle) {
            toggle(button.dataset.toggle, version, button.dataset.active === 'true', button);
        }
    });
    qs('#promptSave').addEventListener('click', (event) => saveVersion(event.currentTarget));
    qs('#promptCancel').addEventListener('click', () => { qs('#promptForm').hidden = true; });
    qs('#promptsSection').hidden = false;
    load();
});
