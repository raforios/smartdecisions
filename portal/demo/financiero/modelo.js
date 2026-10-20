'use strict';

/**
 * Modelo de negocio: a guided form the MANAGER fills once and corrects when
 * the business changes (Rafael, 20-oct: specific fields, its own page). The
 * AI reads it next to the figures —the years, the last twelve months and the
 * projection— and gives its opinion on how well the model matches the
 * results. FINANCE only keeps the form.
 */
document.addEventListener('DOMContentLoaded', async () => {
    if (!window.SD_AUTH.isAuthenticated()) return;

    const F = window.SD_FINANCE;
    const { qs, toast, setButtonBusy } = window.SD_UI;

    const ERRORS = {
        GOAL_MISSING: 'Escribe lo que esperas de este año: las ventas, el margen o los dos.'
    };

    // The form's inputs, by the field FINANCE stores.
    const FIELDS = {
        sells: 'sells', customers: 'customers', cash_sales_percent: 'cashSales',
        credit_days: 'creditDays', main_costs: 'mainCosts', sales_goal: 'salesGoal',
        margin_goal_percent: 'marginGoal', notes: 'notes'
    };
    const NUMBERS = new Set(['cash_sales_percent', 'credit_days', 'sales_goal', 'margin_goal_percent']);

    // What the AI reads; null until a business model is saved.
    let shown = null;
    let figures = null;

    function fill(model) {
        Object.entries(FIELDS).forEach(([field, id]) => {
            qs(`#${id}`).value = model && model[field] != null ? model[field] : '';
        });
    }

    function read() {
        const model = {};
        Object.entries(FIELDS).forEach(([field, id]) => {
            const raw = qs(`#${id}`).value.trim();
            if (raw === '') return;
            model[field] = NUMBERS.has(field) ? Number(raw) : raw;
        });
        return model;
    }

    function noteSaved(updatedAt) {
        qs('#modelNote').textContent = updatedAt
            ? `Guardado el ${new Date(updatedAt).toLocaleString('es-BO')}.`
            : 'Todavía no lo guardaste: la IA lo necesita para compararlo con tus números.';
    }

    function remember(model) {
        shown = model && figures ? { business_model: model, ...figures } : null;
    }

    qs('#modelForm').addEventListener('submit', async (event) => {
        event.preventDefault();
        const model = read();
        if (model.sales_goal == null && model.margin_goal_percent == null) {
            toast(ERRORS.GOAL_MISSING, 'error');
            return;
        }
        const done = setButtonBusy(qs('#modelSave'), 'Guardando…');
        try {
            const answer = await F.put('/business-model', model);
            noteSaved(answer.updated_at);
            remember(answer.business_model);
        } catch (error) {
            const code = error && (error.code || error.message);
            toast(ERRORS[code] || F.errorText(error, 'No se pudo guardar el modelo de negocio.'),
                  'error');
        } finally {
            done();
        }
    });

    try {
        const [stored, data] = await Promise.all([F.get('/business-model'), F.report()]);
        fill(stored.business_model);
        noteSaved(stored.updated_at);
        if (data.months.length) {
            // What the model is compared with, as FINANCE returned it: the year
            // in course and the last complete one, each by its name —the
            // model mistook one for the other in a plain list— and the newest
            // twelve months, because the AI cuts a long list from its start.
            const years = data.years;
            figures = {
                current_year: years[years.length - 1] || null,
                last_complete_year: years[years.length - 2] || null,
                months: data.months.slice(-12),
                notices: data.notices
            };
            try {
                figures.projection = await F.get('/projection');
            } catch (error) {
                // Too little history to project: the comparison goes without it.
                figures.projection = null;
            }
        }
        remember(stored.business_model);
        F.explain('finance_business_model', () => shown, qs('#modelForm'));
    } catch (error) {
        toast(F.errorText(error, 'No se pudo leer el modelo de negocio.'), 'error');
    }
});
