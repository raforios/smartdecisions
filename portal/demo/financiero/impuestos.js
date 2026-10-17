'use strict';

/**
 * Impuestos of the chosen period, and the client's own IUE provision. The
 * suggestion is offered, never applied: until the client saves its own
 * percentage the provision is not calculated (Rafael, 16-oct).
 */
document.addEventListener('DOMContentLoaded', async () => {
    if (!window.SD_AUTH.isAuthenticated()) return;

    const F = window.SD_FINANCE;
    const { qs, toast, setButtonBusy } = window.SD_UI;
    const PROVISION = 'IUE_PROVISION';

    function render(period, data) {
        const taxes = period.taxes;
        qs('#taxesTable tbody').innerHTML = [
            F.moneyRow('IVA a pagar (débito menos crédito fiscal)', taxes.vat_payable, period.exchange),
            F.moneyRow('IT', taxes.transactions_tax, period.exchange),
            F.moneyRow('Provisión del IUE', taxes.income_tax_provision, period.exchange)
        ].join('');
        qs('#ratesLine').textContent = F.ratesLine(period.exchange);
        qs('#notices').innerHTML = F.noticesHtml(period.notices.concat(data.notices));
    }

    async function loadProvision() {
        const answer = await F.get('/parameters');
        const provision = (answer.parameters || []).find((p) => p.parameter_code === PROVISION);
        if (!provision) return;
        const suggested = provision.suggested.toLocaleString('es-BO');
        qs('#provisionHint').textContent = provision.value == null
            ? `Todavía no la definiste. Te sugerimos el ${suggested} %: acéptalo o cambia el porcentaje.`
            : `Guardas el ${provision.value.toLocaleString('es-BO')} % de lo facturado cada mes ` +
              `(la sugerencia es el ${suggested} %).`;
        qs('#provisionValue').value = provision.value == null ? provision.suggested : provision.value;
    }

    qs('#provisionForm').addEventListener('submit', async (event) => {
        event.preventDefault();
        const done = setButtonBusy(qs('#provisionSave'), 'Guardando…');
        try {
            await F.put(`/parameters/${PROVISION}`, { value: Number(qs('#provisionValue').value) });
            qs('#provisionNote').textContent = 'Guardado. El informe ya la calcula.';
            window.location.reload();
        } catch (error) {
            toast(F.errorText(error, 'No se pudo guardar la provisión.'), 'error');
        } finally {
            done();
        }
    });

    try {
        const data = await F.report();
        F.periodSelect(qs('#periodSelect'), data, (period) => render(period, data));
        await loadProvision();
    } catch (error) {
        toast(F.errorText(error, 'No se pudieron leer los impuestos.'), 'error');
    }
});
