/**
 * SalesPage — the issued notes, to reprint, void or take back.
 *
 * A note is not edited: it is already printed and in the buyer's hands. It is
 * voided, and on voiding the units go back exactly to the batches they came
 * from. That is why the screen shows the status and not a form.
 *
 * What a buyer brings back of an accepted invoice is a return: a Nota de
 * Crédito-Débito the SIN receives, which puts the units back on the shelf and
 * the money back in the buyer's hands, and which they get printed and by
 * mail like the invoice.
 */
import { BillingService, PAYMENT_LABELS, errorText } from '../services/BillingService.js';
import { hasRole } from '../../common/js/session/auth.js';
import { invoiceQr, printCreditNote, printTicket, ticketHtml } from './TicketPrinter.js';
import { escapeHtml, money, notify, setBusy, stamp, todayIso, rowIcon } from '../ui.js';

let settings = null;

function rowHtml(note) {
    const cancelled = note.status === 'CANCELLED';
    return `
        <tr data-id="${escapeHtml(note.sale_id)}" class="${cancelled ? 'muted' : ''}"
            ${note.invoice ? `data-invoice="${note.invoice.number}"` : ''}>
            <td><strong>${escapeHtml(note.number)}</strong>
                ${note.invoice ? `<span class="muted">Factura ${note.invoice.number}</span>` : ''}
                ${note.invoice?.emailed_at ? '<span class="badge badge-info">enviada</span>' : ''}
                ${cancelled ? '<span class="badge badge-danger">anulada</span>' : ''}
                ${note.invoice?.reverted_at ? '<span class="badge badge-info">anulación revertida</span>' : ''}</td>
            <td>${stamp(note.created_at)}</td>
            <td>${note.buyer?.name ? escapeHtml(note.buyer.name)
                                   : '<span class="muted">mostrador</span>'}
                ${note.buyer?.document
                    ? `<span class="muted">${escapeHtml(note.buyer.document)}</span>` : ''}</td>
            <td>${note.payments?.length > 1 ? 'Combinado'
                : escapeHtml(PAYMENT_LABELS[note.payment_method] || note.payment_method)}</td>
            <td class="numeric">${note.lines.length}</td>
            <td class="numeric">${money(note.total)}</td>
            <td class="numeric">${cancelled ? '—' : money(note.margin)}</td>
            <td>
                <button type="button" class="btn-icon view" data-tip="Ver" aria-label="Ver">${rowIcon('eye')}</button>
                <button type="button" class="btn-icon print" data-tip="Imprimir" aria-label="Imprimir">${rowIcon('print')}</button>
                ${note.invoice && note.buyer?.email
                    ? `<button type="button" class="btn-icon mail" data-tip="Enviar por correo" aria-label="Enviar por correo">${rowIcon('mail')}</button>` : ''}
                ${!cancelled && note.invoice?.state === 'ACCEPTED' && hasRole('ADMIN', 'MANAGER')
                    ? `<button type="button" class="btn-icon return" data-tip="Devolución" aria-label="Devolución">${rowIcon('undo')}</button>` : ''}
                ${!cancelled && !note.invoice?.reverted_at && hasRole('ADMIN', 'MANAGER')
                    ? `<button type="button" class="btn-icon is-delete cancel" data-tip="Anular" aria-label="Anular">${rowIcon('close')}</button>` : ''}
                ${cancelled && note.invoice?.cancelled_at_sin && !note.invoice.reverted_at
                    && hasRole('ADMIN', 'MANAGER')
                    ? `<button type="button" class="btn-icon revert" data-tip="Revertir anulación" aria-label="Revertir anulación">${rowIcon('refresh')}</button>`
                    : ''}
            </td>
        </tr>`;
}

async function load(host) {
    const body = host.querySelector('#sales-body');
    body.innerHTML = '<tr class="empty-row"><td colspan="8">Cargando…</td></tr>';
    try {
        const page = await BillingService.listSales({
            date_from: host.querySelector('#from').value,
            date_to: host.querySelector('#to').value
        });
        body.innerHTML = page.items.length
            ? page.items.map(rowHtml).join('')
            : '<tr class="empty-row"><td colspan="8">No hay notas en ese rango.</td></tr>';
        host.querySelector('#summary').textContent =
            `${page.total} nota(s) · Bs ${money(page.total_amount)} cobrados`;
    } catch (error) {
        body.innerHTML = `<tr class="empty-row"><td colspan="8">${
            escapeHtml(errorText(error, 'No se pudieron leer las notas.'))}</td></tr>`;
    }
}

/**
 * Opens the panel that cancels an invoice, with the SIN's reasons.
 *
 * @param {HTMLElement} host Where the section mounts.
 * @param {string} saleId Note to cancel.
 * @param {string} number Its invoice number.
 */
async function askCancellationReason(host, saleId, number) {
    const panel = host.querySelector('#cancel-panel');
    try {
        const { entries } = await BillingService.siatCatalog('CANCELLATION_REASONS');
        host.querySelector('#cancel-reason').innerHTML = entries.map((reason) =>
            `<option value="${escapeHtml(reason.code)}">${escapeHtml(reason.description)}</option>`
        ).join('');
    } catch (error) {
        notify(errorText(error, 'No se pudieron leer los motivos del SIN.'), 'error');
        return;
    }
    host.querySelector('#cancel-title').textContent = `Anular factura ${number}`;
    panel.dataset.saleId = saleId;
    panel.dataset.number = number;
    panel.hidden = false;
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

/**
 * Wires the cancellation panel once.
 *
 * @param {HTMLElement} host Where the section mounts.
 */
function wireCancelPanel(host) {
    const panel = host.querySelector('#cancel-panel');
    host.querySelector('#cancel-back').addEventListener('click', () => { panel.hidden = true; });
    host.querySelector('#cancel-confirm').addEventListener('click', async (event) => {
        const done = setBusy(event.currentTarget, 'Anulando…');
        try {
            await BillingService.cancelSale(panel.dataset.saleId,
                                            Number(host.querySelector('#cancel-reason').value));
            notify(`Factura ${panel.dataset.number} anulada en el SIN.`, 'success');
            panel.hidden = true;
            await load(host);
        } catch (error) {
            notify(errorText(error, 'No se pudo anular.'), 'error');
        } finally {
            done();
        }
    });
}

/** Units of each SKU already given back by the notes the SIN holds. */
function returnedBySku(notes) {
    const back = {};
    for (const note of notes.filter((one) => one.state === 'ACCEPTED')) {
        for (const line of note.lines) back[line.sku] = (back[line.sku] || 0) + line.quantity;
    }
    return back;
}

/**
 * Paints the returns of a sale and the form for a new one.
 *
 * @param {HTMLElement} host Where the section mounts.
 * @param {object} sale The sale, with its invoice.
 */
async function showReturns(host, sale) {
    const panel = host.querySelector('#return-panel');
    let notes = [];
    try {
        notes = (await BillingService.listReturns(sale.sale_id)).items;
    } catch (error) {
        notify(errorText(error, 'No se pudieron leer las devoluciones.'), 'error');
        return;
    }
    const back = returnedBySku(notes);
    panel.dataset.saleId = sale.sale_id;
    host.querySelector('#return-title').textContent =
        `Devoluciones de la factura ${sale.invoice.number}`;
    host.querySelector('#return-notes').innerHTML = notes.length ? `
        <table class="data-table">
            <thead><tr><th>Nota</th><th>Fecha</th><th class="numeric">Devuelto</th><th></th></tr></thead>
            <tbody>${notes.map((note) => `
                <tr data-note="${escapeHtml(note.credit_note_id)}"
                    class="${note.state === 'CANCELLED' ? 'muted' : ''}">
                    <td><strong>${note.number}</strong>
                        ${note.emailed_at ? '<span class="badge badge-info">enviada</span>' : ''}
                        ${note.state === 'CANCELLED'
                            ? '<span class="badge badge-danger">anulada</span>' : ''}
                        ${note.reverted_at ? '<span class="badge badge-info">anulación revertida</span>' : ''}</td>
                    <td>${stamp(note.created_at)}</td>
                    <td class="numeric">${money(note.amount_returned)}</td>
                    <td><button type="button" class="btn-icon print-note" data-tip="Imprimir" aria-label="Imprimir">${rowIcon('print')}</button>
                        ${note.state === 'ACCEPTED' && !note.reverted_at
                            ? `<button type="button" class="btn-icon is-delete cancel-note" data-tip="Anular" aria-label="Anular">${rowIcon('close')}</button>`
                            : ''}
                        ${note.state === 'CANCELLED' && !note.reverted_at
                            ? `<button type="button" class="btn-icon revert-note" data-tip="Revertir anulación" aria-label="Revertir anulación">${rowIcon('refresh')}</button>`
                            : ''}</td>
                </tr>`).join('')}</tbody>
        </table>` : '<p class="muted small">Esta factura no tiene devoluciones.</p>';
    host.querySelector('#return-lines').innerHTML = sale.lines.map((line) => {
        const left = line.quantity - (back[line.sku] || 0);
        return `
            <tr>
                <td>${escapeHtml(line.sku)} - ${escapeHtml(line.description)}</td>
                <td class="numeric">${money(line.quantity)}</td>
                <td class="numeric">${money(back[line.sku] || 0)}</td>
                <td class="numeric"><input type="number" class="return-quantity" min="0"
                    max="${left}" step="any" value="0" data-sku="${escapeHtml(line.sku)}"
                    ${left > 0 ? '' : 'disabled'}></td>
            </tr>`;
    }).join('');
    panel.hidden = false;
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

/**
 * Wires the returns panel once: a new return, printing a note and
 * cancelling one with the SIN's reason.
 *
 * @param {HTMLElement} host Where the section mounts.
 */
function wireReturnPanel(host) {
    const panel = host.querySelector('#return-panel');
    const refresh = async () => showReturns(host, await BillingService.getSale(panel.dataset.saleId));
    host.querySelector('#return-back').addEventListener('click', () => { panel.hidden = true; });

    host.querySelector('#return-confirm').addEventListener('click', async (event) => {
        const lines = [...host.querySelectorAll('.return-quantity')]
            .map((input) => ({ sku: input.dataset.sku, quantity: Number(input.value) }))
            .filter((line) => line.quantity > 0);
        if (!lines.length) {
            notify('Indica cuántas unidades devuelve el cliente.', 'error');
            return;
        }
        const done = setBusy(event.currentTarget, 'Emitiendo…');
        try {
            const note = await BillingService.returnSale(panel.dataset.saleId, lines);
            const sale = await BillingService.getSale(panel.dataset.saleId);
            notify(`Nota de crédito-débito ${note.number} aceptada por el SIN.`, 'success');
            printCreditNote(sale, note, settings, settings.ticket_width);
            await showReturns(host, sale);
        } catch (error) {
            notify(errorText(error, 'No se pudo registrar la devolución.'), 'error');
        } finally {
            done();
        }
    });

    host.querySelector('#return-notes').addEventListener('click', async (event) => {
        const row = event.target.closest('tr[data-note]');
        if (!row) return;
        const sale = await BillingService.getSale(panel.dataset.saleId);
        const note = (await BillingService.listReturns(sale.sale_id)).items
            .find((one) => one.credit_note_id === row.dataset.note);
        if (event.target.classList.contains('print-note')) {
            printCreditNote(sale, note, settings, settings.ticket_width);
            return;
        }
        if (event.target.classList.contains('cancel-note')) {
            await openNoteCancel(host, note);
            return;
        }
        if (event.target.classList.contains('revert-note')) {
            await revert(event.target, `la nota de crédito-débito ${note.number}`,
                         () => BillingService.revertReturn(sale.sale_id, note.credit_note_id),
                         refresh);
        }
    });

    host.querySelector('#note-cancel-back').addEventListener('click', () => {
        host.querySelector('#note-cancel').hidden = true;
    });
    host.querySelector('#note-cancel-confirm').addEventListener('click', async (event) => {
        const box = host.querySelector('#note-cancel');
        const done = setBusy(event.currentTarget, 'Anulando…');
        try {
            await BillingService.cancelReturn(panel.dataset.saleId, box.dataset.noteId,
                                              Number(host.querySelector('#note-cancel-reason').value));
            notify(`Nota de crédito-débito ${box.dataset.number} anulada en el SIN.`, 'success');
            box.hidden = true;
            await refresh();
        } catch (error) {
            notify(errorText(error, 'No se pudo anular la nota.'), 'error');
        } finally {
            done();
        }
    });
}

/**
 * Reverts the cancellation of an invoice or a note at the SIN, once asked:
 * the SIN allows it only once and the document can never be cancelled again.
 *
 * @param {HTMLElement} button The button pressed.
 * @param {string} name How the question names the document.
 * @param {Function} request The call that reverts it.
 * @param {Function} after What to repaint once it is valid again.
 */
async function revert(button, name, request, after) {
    if (!window.confirm(`¿Revertir la anulación de ${name}? Vuelve a ser válida, se avisa al `
                        + 'cliente y ya no se podrá anular de nuevo.')) {
        return;
    }
    const done = setBusy(button, '…');
    try {
        await request();
        notify(`La anulación de ${name} se revirtió en el SIN.`, 'success');
        await after();
    } catch (error) {
        notify(errorText(error, 'No se pudo revertir la anulación.'), 'error');
    } finally {
        done();
    }
}

/**
 * Opens the box that cancels a note, with the SIN's reasons.
 *
 * @param {HTMLElement} host Where the section mounts.
 * @param {object} note The note to cancel.
 */
async function openNoteCancel(host, note) {
    const select = host.querySelector('#note-cancel-reason');
    if (!select.options.length) {
        try {
            const { entries } = await BillingService.siatCatalog('CANCELLATION_REASONS');
            select.innerHTML = entries.map((reason) =>
                `<option value="${escapeHtml(reason.code)}">${escapeHtml(reason.description)}</option>`
            ).join('');
        } catch (error) {
            notify(errorText(error, 'No se pudieron leer los motivos del SIN.'), 'error');
            return;
        }
    }
    const box = host.querySelector('#note-cancel');
    box.dataset.noteId = note.credit_note_id;
    box.dataset.number = note.number;
    host.querySelector('#note-cancel-title').textContent =
        `Anular nota de crédito-débito ${note.number}`;
    box.hidden = false;
}

/**
 * Paints the sales of the chosen range.
 *
 * @param {HTMLElement} host Where the section mounts.
 */
export async function mountSales(host) {
    settings = await BillingService.getSettings();

    host.innerHTML = `
        <header class="sd-page-head"><div>
            <h1>Ventas</h1>
            <p class="muted">Una nota no se edita: se anula, y sus unidades vuelven
               a los lotes de los que salieron.</p>
        </div></header>

        <section class="card">
            <div class="field-row">
                <label class="field"><span>Desde</span>
                    <input type="date" id="from" value="${todayIso(-7)}"></label>
                <label class="field"><span>Hasta</span>
                    <input type="date" id="to" value="${todayIso()}"></label>
                <button class="btn btn-secondary" id="reload" data-btn-icon="filter">Buscar</button>
            </div>
            <p class="muted small" id="summary"></p>

            <div class="table-wrapper">
                <table class="data-table">
                    <thead>
                        <tr><th>Nota</th><th>Fecha</th><th>Cliente</th><th>Pago</th>
                            <th class="numeric">Líneas</th><th class="numeric">Total</th>
                            <th class="numeric">Margen</th><th></th></tr>
                    </thead>
                    <tbody id="sales-body"></tbody>
                </table>
            </div>
        </section>

        <!-- An invoice is cancelled at the SIN too, and the SIN asks why:
             the reason comes from its own catalogue. -->
        <section class="card" id="cancel-panel" hidden>
            <h3 id="cancel-title">Anular factura</h3>
            <label class="field">
                <span>Motivo de la anulación</span>
                <select id="cancel-reason"></select>
            </label>
            <p class="muted small">Se anula en Impuestos Nacionales y las unidades
               vuelven a stock. No se puede deshacer.</p>
            <div class="form-actions">
                <button class="btn btn-delete" id="cancel-confirm" data-btn-icon="close" type="button">Anular</button>
                <button class="btn btn-cancel" id="cancel-back" data-btn-icon="chevronLeft" type="button">Volver</button>
            </div>
        </section>

        <!-- A return is a Nota de Crédito-Débito: the SIN receives it, the
             units go back to stock and the money back to the buyer. -->
        <section class="card" id="return-panel" hidden>
            <h3 id="return-title">Devoluciones</h3>
            <div class="table-wrapper" id="return-notes"></div>
            <div id="note-cancel" hidden>
                <h4 id="note-cancel-title">Anular nota de crédito-débito</h4>
                <label class="field">
                    <span>Motivo de la anulación</span>
                    <select id="note-cancel-reason"></select>
                </label>
                <p class="muted small">Se anula en Impuestos Nacionales: las unidades vuelven a
                   salir de stock y la devolución deja de contar en la caja.</p>
                <div class="form-actions">
                    <button class="btn btn-delete" id="note-cancel-confirm" data-btn-icon="close" type="button">Anular nota</button>
                    <button class="btn btn-cancel" id="note-cancel-back" data-btn-icon="chevronLeft" type="button">Volver</button>
                </div>
            </div>
            <h4>Nueva devolución</h4>
            <div class="table-wrapper">
                <table class="data-table">
                    <thead><tr><th>Producto</th><th class="numeric">Vendido</th>
                        <th class="numeric">Ya devuelto</th><th class="numeric">Devuelve</th></tr></thead>
                    <tbody id="return-lines"></tbody>
                </table>
            </div>
            <p class="muted small">Se emite una nota de crédito-débito a Impuestos Nacionales;
               si la acepta, las unidades vuelven a stock y el efectivo sale de tu caja.</p>
            <div class="form-actions">
                <button class="btn btn-primary" id="return-confirm" data-btn-icon="undo" type="button">Devolver</button>
                <button class="btn btn-cancel" id="return-back" data-btn-icon="chevronLeft" type="button">Volver</button>
            </div>
        </section>

        <section class="card" id="detail" hidden>
            <h3 id="detail-title">Nota</h3>
            <div class="ticket-preview"><iframe id="preview" title="Vista de la nota"></iframe></div>
        </section>`;

    wireCancelPanel(host);
    wireReturnPanel(host);
    await load(host);
    host.querySelector('#reload').addEventListener('click', () => load(host));

    host.querySelector('#sales-body').addEventListener('click', async (event) => {
        const row = event.target.closest('tr[data-id]');
        if (!row) return;
        const saleId = row.dataset.id;

        if (event.target.classList.contains('view')) {
            const note = await BillingService.getSale(saleId);
            host.querySelector('#detail').hidden = false;
            host.querySelector('#detail-title').textContent = `Nota ${note.number}`;
            const frame = host.querySelector('#preview');
            frame.srcdoc = ticketHtml(note, settings, settings.ticket_width,
                                      await invoiceQr(note));
            host.querySelector('#detail').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            return;
        }

        if (event.target.classList.contains('print')) {
            printTicket(await BillingService.getSale(saleId), settings, settings.ticket_width);
            return;
        }

        if (event.target.classList.contains('mail')) {
            // The invoice goes to the address the buyer gave at the counter;
            // sending again is how a failed or lost mail is fixed.
            const done = setBusy(event.target, '…');
            try {
                const note = await BillingService.resendInvoice(saleId);
                notify(`Factura ${note.invoice.number} enviada a ${note.buyer.email}.`, 'success');
                await load(host);
            } catch (error) {
                notify(errorText(error, 'No se pudo enviar la factura.'), 'error');
            } finally {
                done();
            }
            return;
        }

        if (event.target.classList.contains('return')) {
            await showReturns(host, await BillingService.getSale(saleId));
            return;
        }

        if (event.target.classList.contains('revert')) {
            await revert(event.target, `la factura ${row.dataset.invoice}`,
                         () => BillingService.revertSale(saleId), () => load(host));
            return;
        }

        if (event.target.classList.contains('cancel') && row.dataset.invoice) {
            await askCancellationReason(host, saleId, row.dataset.invoice);
            return;
        }

        if (event.target.classList.contains('cancel')) {
            // Voiding returns stock: it is asked once, with the number in
            // view, because there is no way back afterwards.
            const number = row.querySelector('strong').textContent;
            if (!window.confirm(`¿Anular la nota ${number}? Las unidades vuelven a stock.`)) {
                return;
            }
            const done = setBusy(event.target, '…');
            try {
                await BillingService.cancelSale(saleId);
                notify(`Nota ${number} anulada.`, 'success');
                await load(host);
            } catch (error) {
                notify(errorText(error, 'No se pudo anular.'), 'error');
            } finally {
                done();
            }
        }
    });
}
