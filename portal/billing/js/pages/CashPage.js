/**
 * CashPage — the till of whoever is at the counter.
 *
 * Three moments of the same shift: open with the counted cash, record what
 * goes out (expenses) and close counting again. Before closing, everything in
 * the shift is shown, and the note comes prefilled with the difference so the
 * cashier only adds the reason.
 *
 * Only cash is counted: QR and cards are shown to reconcile them with the
 * bank and the POS.
 */
import {
    BillingService,
    EXPENSE_LABELS,
    PAYMENT_LABELS,
    currentTillOrNull,
    errorText
} from '../services/BillingService.js';
import { escapeHtml, money, notify, setBusy, shortDate, stamp } from '../ui.js';

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
                <td class="num">${row.count}</td>
                <td class="num">${money(row.total)}</td></tr>`).join('')
        : '<tr><td colspan="3" class="muted">Sin ventas en este turno.</td></tr>';
    const expenses = till.expenses.length
        ? till.expenses.map((row) => `
            <tr><td>${escapeHtml(EXPENSE_LABELS[row.expense_type] || row.expense_type)}</td>
                <td class="num">${row.count}</td>
                <td class="num">${money(row.total)}</td></tr>`).join('')
        : '<tr><td colspan="3" class="muted">Sin egresos.</td></tr>';

    return `
        <div class="kpi-grid">
            <div class="card kpi"><span class="label">Efectivo inicial</span>
                <span class="value">Bs ${money(till.opening_cash)}</span>
                <span class="foot">Abierta ${stamp(till.opened_at)}</span></div>
            <div class="card kpi"><span class="label">Ventas del turno</span>
                <span class="value">Bs ${money(till.income_total)}</span>
                <span class="foot">todos los medios de pago</span></div>
            <div class="card kpi"><span class="label">Egresos</span>
                <span class="value">Bs ${money(till.expenses_total)}</span>
                <span class="foot">salieron en efectivo</span></div>
            <div class="card kpi"><span class="label">Efectivo esperado</span>
                <span class="value">Bs ${money(till.expected_cash)}</span>
                <span class="foot">inicial + ventas en efectivo − egresos</span></div>
        </div>
        <div class="panel-grid">
            <section class="card">
                <h3>Ingresos por medio de pago</h3>
                <p class="muted small">QR y tarjetas no están en el cajón: se concilian
                   con el banco y el POS.</p>
                <div class="table-scroll"><table class="data-table">
                    <thead><tr><th>Medio</th><th class="num">Ventas</th>
                               <th class="num">Bs</th></tr></thead>
                    <tbody>${income}</tbody>
                </table></div>
            </section>
            <section class="card">
                <h3>Egresos por tipo</h3>
                <div class="table-scroll"><table class="data-table">
                    <thead><tr><th>Tipo</th><th class="num">Cantidad</th>
                               <th class="num">Bs</th></tr></thead>
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
            <button class="btn btn-primary" id="close-till" disabled>Cerrar caja</button>
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
        <header class="page-head">
            <h2>Caja</h2>
            <p class="muted">Para vender, abre tu caja con el efectivo que hay en el cajón.</p>
        </header>
        <section class="card">
            <div class="field-row">
                <label class="field"><span>Efectivo inicial (Bs)</span>
                    <input type="number" id="opening" min="0" step="0.01" value="0"></label>
            </div>
            <button class="btn btn-primary" id="open-till">Abrir caja</button>
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
    return `<div class="table-scroll"><table class="data-table">
        <thead><tr><th>Hora</th><th>Tipo</th><th>Concepto</th>
                   <th class="num">Bs</th><th></th></tr></thead>
        <tbody>${till.movements.map((row) => `
            <tr class="${row.status === 'CANCELLED' ? 'muted' : ''}">
                <td>${stamp(row.created_at)}</td>
                <td>${escapeHtml(EXPENSE_LABELS[row.expense_type] || row.expense_type)}</td>
                <td>${escapeHtml(row.concept)}</td>
                <td class="num">${money(row.amount)}</td>
                <td>${row.status === 'CANCELLED'
                    ? `<span class="chip chip-muted">Anulado por ${escapeHtml(row.cancelled_by)}</span>`
                    : `<button class="link-danger cancel-expense"
                               data-id="${escapeHtml(row.movement_id)}">Anular</button>`}</td>
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
        <header class="page-head">
            <h2>Caja y egresos</h2>
            <p class="muted">Turno del ${shortDate(till.business_day)}.
               ${till.expired ? '<strong class="danger">Es de un día anterior: ciérrala para '
                   + 'poder vender hoy.</strong>' : ''}</p>
        </header>
        ${tillSummaryHtml(till)}
        <section class="card" ${till.expired ? 'hidden' : ''}>
            <h3>Registrar un egreso</h3>
            <p class="muted small">Sólo el efectivo que sale de esta caja. Lo que se paga
               por banco no va aquí.</p>
            <div class="field-row">
                <label class="field"><span>Tipo</span>
                    <select id="expense-type">${Object.entries(EXPENSE_LABELS).map(
                        ([value, label]) => `<option value="${value}">${label}</option>`).join('')}
                    </select></label>
                <label class="field"><span>Monto (Bs)</span>
                    <input type="number" id="expense-amount" min="0.01" step="0.01"></label>
                <label class="field"><span>Concepto</span>
                    <input type="text" id="expense-concept" maxlength="200"
                           placeholder="A quién y por qué"></label>
            </div>
            <button class="btn btn-secondary" id="add-expense">Registrar egreso</button>
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
