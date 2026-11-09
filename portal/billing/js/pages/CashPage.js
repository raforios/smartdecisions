/**
 * CashPage — the till of whoever is at the counter.
 *
 * Three moments of the same shift: open with the counted cash, record what
 * goes out (expenses) and close counting again. Before closing, everything in
 * the shift is shown, and the note comes prefilled with the difference so the
 * cashier only adds the reason.
 *
 * Only cash is counted: transfers, wallets and cards are shown to reconcile
 * them with the bank and the POS.
 */
import {
    BillingService,
    EXPENSE_LABELS,
    MANUAL_EXPENSE_TYPES,
    PAYMENT_LABELS,
    currentTillOrNull,
    errorText
} from '../services/BillingService.js';
import { escapeHtml, money, notify, setBusy, shortDate, stamp, rowIcon } from '../ui.js';

/** The initial note, according to the difference. The user completes it. */
export function differenceNote(difference) {
    if (Math.abs(difference) < 0.005) return 'Sin diferencia.';
    return difference < 0
        ? `Faltan Bs ${money(-difference)}.`
        : `Sobran Bs ${money(difference)}.`;
}

/** The count of a till: income by method, expenses by type and the expected amount. */
export function tillSummaryHtml(till) {
    const income = till.income.length
        ? till.income.map((row) => `
            <tr><td>${escapeHtml(PAYMENT_LABELS[row.payment_method] || row.payment_method)}</td>
                <td class="numeric">${row.count}</td>
                <td class="numeric">${money(row.total)}</td></tr>`).join('')
        : '<tr><td colspan="3" class="muted">Sin ventas en este turno.</td></tr>';
    const expenses = till.expenses.length
        ? till.expenses.map((row) => `
            <tr><td>${escapeHtml(EXPENSE_LABELS[row.expense_type] || row.expense_type)}</td>
                <td class="numeric">${row.count}</td>
                <td class="numeric">${money(row.total)}</td></tr>`).join('')
        : '<tr><td colspan="3" class="muted">Sin egresos.</td></tr>';

    return `
        <div class="sd-grid sd-grid-quarters">
            <div class="sd-stat"><p class="sd-stat-label">Efectivo inicial</p>
                <p class="sd-stat-value">Bs ${money(till.opening_cash)}</p>
                <p class="sd-stat-other">Abierta ${stamp(till.opened_at)}</p></div>
            <div class="sd-stat"><p class="sd-stat-label">Ventas del turno</p>
                <p class="sd-stat-value">Bs ${money(till.income_total)}</p>
                <p class="sd-stat-other">todos los medios de pago</p></div>
            <div class="sd-stat"><p class="sd-stat-label">Egresos</p>
                <p class="sd-stat-value">Bs ${money(till.expenses_total)}</p>
                <p class="sd-stat-other">salieron en efectivo</p></div>
            <div class="sd-stat"><p class="sd-stat-label">Efectivo esperado</p>
                <p class="sd-stat-value">Bs ${money(till.expected_cash)}</p>
                <p class="sd-stat-other">inicial + ventas en efectivo − egresos</p></div>
        </div>
        <div class="sd-grid sd-grid-half">
            <section class="card">
                <h3>Ingresos por medio de pago</h3>
                <p class="muted small">Transferencias, billeteras y tarjetas no están en el cajón: se concilian
                   con el banco y el POS.</p>
                <div class="table-wrapper"><table class="data-table">
                    <thead><tr><th>Medio</th><th class="numeric">Ventas</th>
                               <th class="numeric">Bs</th></tr></thead>
                    <tbody>${income}</tbody>
                </table></div>
            </section>
            <section class="card">
                <h3>Egresos por tipo</h3>
                <div class="table-wrapper"><table class="data-table">
                    <thead><tr><th>Tipo</th><th class="numeric">Cantidad</th>
                               <th class="numeric">Bs</th></tr></thead>
                    <tbody>${expenses}</tbody>
                </table></div>
            </section>
        </div>`;
}

/**
 * Closing form: counted cash, live difference and prefilled note. Used by the
 * user's own till and by the manager's screen.
 *
 * @param {HTMLElement} holder Where it is painted.
 * @param {object} till The open till.
 * @param {{noteRequired: boolean, onClosed: Function}} options
 */
export function mountCloseForm(holder, till, { noteRequired, onClosed }) {
    holder.innerHTML = `
        <section class="card">
            <h3>Cierre de caja</h3>
            <p class="muted small">Cuenta el efectivo del cajón. La observación se
               completa sola con la diferencia; agrega lo que haga falta.</p>
            <div class="field-row">
                <label class="field"><span>Efectivo contado (Bs)</span>
                    <input type="number" id="counted" min="0" step="0.01"></label>
                <div class="field"><span>Diferencia</span>
                    <strong id="difference">—</strong></div>
            </div>
            <label class="field"><span>Observación${noteRequired ? ' (obligatoria)' : ''}</span>
                <textarea id="close-note" maxlength="500" rows="2"></textarea></label>
            <button class="btn btn-save" id="close-till" data-btn-icon="lock" disabled>Cerrar caja</button>
        </section>`;

    const counted = holder.querySelector('#counted');
    const note = holder.querySelector('#close-note');
    const button = holder.querySelector('#close-till');
    let prefilled = '';

    counted.addEventListener('input', () => {
        const value = counted.value === '' ? null : Number(counted.value);
        button.disabled = value === null;
        if (value === null) return;
        const difference = value - till.expected_cash;
        holder.querySelector('#difference').textContent =
            `Bs ${money(difference)} — ${differenceNote(difference)}`;
        // The note is replaced while it is still the prefilled one; if the
        // user already wrote, their text is kept and only the beginning changes.
        const next = differenceNote(difference);
        note.value = note.value.startsWith(prefilled)
            ? next + note.value.slice(prefilled.length)
            : note.value;
        prefilled = next;
    });

    button.addEventListener('click', async () => {
        if (noteRequired && note.value.trim() === prefilled.trim()) {
            notify('Explica por qué cierras la caja de otra persona.', 'error');
            return;
        }
        const done = setBusy(button, 'Cerrando…');
        try {
            const closed = await BillingService.closeTill(till.session_id, {
                counted_cash: Number(counted.value),
                note: note.value.trim() || null
            });
            notify(`Caja cerrada. Diferencia Bs ${money(closed.difference)}.`, 'success');
            await onClosed(closed);
        } catch (error) {
            notify(errorText(error, 'No se pudo cerrar la caja.'), 'error');
            done();
        }
    });
}

function mountOpenForm(host) {
    host.innerHTML = `
        <header class="sd-page-head"><div>
            <h1>Caja</h1>
            <p class="muted">Para vender, abre tu caja con el efectivo que hay en el cajón.</p>
        </div></header>
        <section class="card">
            <div class="field-row">
                <label class="field"><span>Efectivo inicial (Bs)</span>
                    <input type="number" id="opening" min="0" step="0.01" value="0"></label>
            </div>
            <button class="btn btn-primary" id="open-till" data-btn-icon="power">Abrir caja</button>
        </section>`;
    host.querySelector('#open-till').addEventListener('click', async (event) => {
        const done = setBusy(event.currentTarget, 'Abriendo…');
        try {
            await BillingService.openTill(Number(host.querySelector('#opening').value || 0));
            notify('Caja abierta.', 'success');
            await mountCash(host);
        } catch (error) {
            notify(errorText(error, 'No se pudo abrir la caja.'), 'error');
            done();
        }
    });
}

function movementsHtml(till) {
    if (!till.movements.length) return '<p class="muted small">Sin egresos en este turno.</p>';
    return `<div class="table-wrapper"><table class="data-table">
        <thead><tr><th>Hora</th><th>Tipo</th><th>Concepto</th>
                   <th class="numeric">Bs</th><th></th></tr></thead>
        <tbody>${till.movements.map((row) => `
            <tr class="${row.status === 'CANCELLED' ? 'muted' : ''}">
                <td>${stamp(row.created_at)}</td>
                <td>${escapeHtml(EXPENSE_LABELS[row.expense_type] || row.expense_type)}</td>
                <td>${escapeHtml(row.concept)}</td>
                <td class="numeric">${money(row.amount)}</td>
                <td>${row.status === 'CANCELLED'
                    ? `<span class="badge badge-muted">Anulado por ${escapeHtml(row.cancelled_by)}</span>`
                    : row.expense_type === 'REFUND'
                    ? '<span class="badge badge-muted">Por nota de crédito-débito</span>'
                    : `<button type="button" class="btn-icon is-delete cancel-expense" data-tip="Anular" aria-label="Anular"
                               data-id="${escapeHtml(row.movement_id)}">${rowIcon('close')}</button>`}</td>
            </tr>`).join('')}</tbody>
    </table></div>`;
}

/**
 * Paints the user's till and wires it.
 *
 * @param {HTMLElement} host Where the section mounts.
 */
export async function mountCash(host) {
    const till = await currentTillOrNull();
    if (!till) {
        mountOpenForm(host);
        return;
    }

    host.innerHTML = `
        <header class="sd-page-head"><div>
            <h1>Caja y egresos</h1>
            <p class="muted">Turno del ${shortDate(till.business_day)}.
               ${till.expired ? '<strong class="danger">Es de un día anterior: ciérrala para '
                   + 'poder vender hoy.</strong>' : ''}</p>
        </div></header>
        ${tillSummaryHtml(till)}
        <section class="card" ${till.expired ? 'hidden' : ''}>
            <h3>Registrar un egreso</h3>
            <p class="muted small">Sólo el efectivo que sale de esta caja. Lo que se paga
               por banco no va aquí.</p>
            <div class="field-row">
                <label class="field"><span>Tipo</span>
                    <select id="expense-type">${MANUAL_EXPENSE_TYPES.map((value) =>
                        `<option value="${value}">${EXPENSE_LABELS[value]}</option>`).join('')}
                    </select></label>
                <label class="field"><span>Monto (Bs)</span>
                    <input type="number" id="expense-amount" min="0.01" step="0.01"></label>
                <label class="field"><span>Concepto</span>
                    <input type="text" id="expense-concept" maxlength="200"
                           placeholder="A quién y por qué"></label>
            </div>
            <button class="btn btn-primary" id="add-expense" data-btn-icon="plus">Registrar egreso</button>
        </section>
        <section class="card">
            <h3>Egresos del turno</h3>
            <div id="movements">${movementsHtml(till)}</div>
        </section>
        <div id="close-holder"></div>`;

    const add = host.querySelector('#add-expense');
    add?.addEventListener('click', async () => {
        const done = setBusy(add, 'Registrando…');
        try {
            await BillingService.addExpense(till.session_id, {
                expense_type: host.querySelector('#expense-type').value,
                amount: Number(host.querySelector('#expense-amount').value),
                concept: host.querySelector('#expense-concept').value.trim()
            });
            notify('Egreso registrado.', 'success');
            await mountCash(host);
        } catch (error) {
            notify(errorText(error, 'No se pudo registrar el egreso.'), 'error');
            done();
        }
    });

    host.querySelector('#movements').addEventListener('click', async (event) => {
        const button = event.target.closest('.cancel-expense');
        if (!button) return;
        try {
            await BillingService.cancelExpense(till.session_id, button.dataset.id);
            notify('Egreso anulado.', 'success');
            await mountCash(host);
        } catch (error) {
            notify(errorText(error, 'No se pudo anular el egreso.'), 'error');
        }
    });

    mountCloseForm(host.querySelector('#close-holder'), till, {
        noteRequired: false,
        onClosed: () => mountCash(host)
    });
}
