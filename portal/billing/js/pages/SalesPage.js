/**
 * SalesPage — las notas emitidas, para reimprimir o anular.
 *
 * Una nota no se edita: ya está impresa y en manos del comprador. Se anula, y
 * al anularla las unidades vuelven exactamente a los lotes de los que
 * salieron. Por eso la pantalla muestra el estado y no un formulario.
 */
import { BillingService, errorText } from '../services/BillingService.js';
import { hasRole } from '../auth.js';
import { printTicket, ticketHtml } from './TicketPrinter.js';
import { escapeHtml, money, notify, setBusy, stamp, todayIso } from '../ui.js';

let settings = null;

function rowHtml(note) {
    const cancelled = note.status === 'CANCELLED';
    return `
        <tr data-id="${escapeHtml(note.sale_id)}" class="${cancelled ? 'muted' : ''}">
            <td><strong>${escapeHtml(note.number)}</strong>
                ${cancelled ? '<span class="chip chip-danger">anulada</span>' : ''}</td>
            <td>${stamp(note.created_at)}</td>
            <td>${note.buyer?.name ? escapeHtml(note.buyer.name)
                                   : '<span class="muted">mostrador</span>'}
                ${note.buyer?.document
                    ? `<span class="muted">${escapeHtml(note.buyer.document)}</span>` : ''}</td>
            <td>${escapeHtml(note.payment_method)}</td>
            <td class="num">${note.lines.length}</td>
            <td class="num">${money(note.total)}</td>
            <td class="num">${cancelled ? '—' : money(note.margin)}</td>
            <td>
                <button class="btn btn-ghost btn-small view">Ver</button>
                <button class="btn btn-ghost btn-small print">Imprimir</button>
                ${!cancelled && hasRole('ADMIN', 'MANAGER')
                    ? '<button class="btn btn-ghost btn-small cancel">Anular</button>' : ''}
            </td>
        </tr>`;
}

async function load(host) {
    const body = host.querySelector('#sales-body');
    body.innerHTML = '<tr class="empty"><td colspan="8">Cargando…</td></tr>';
    try {
        const page = await BillingService.listSales({
            date_from: host.querySelector('#from').value,
            date_to: host.querySelector('#to').value
        });
        body.innerHTML = page.items.length
            ? page.items.map(rowHtml).join('')
            : '<tr class="empty"><td colspan="8">No hay notas en ese rango.</td></tr>';
        host.querySelector('#summary').textContent =
            `${page.total} nota(s) · Bs ${money(page.total_amount)} cobrados`;
    } catch (error) {
        body.innerHTML = `<tr class="empty"><td colspan="8">${
            escapeHtml(errorText(error, 'No se pudieron leer las notas.'))}</td></tr>`;
    }
}

/**
 * Pinta las ventas del rango elegido.
 *
 * @param {HTMLElement} host Dónde se monta la sección.
 */
export async function mountSales(host) {
    settings = await BillingService.getSettings();

    host.innerHTML = `
        <header class="page-head">
            <h2>Ventas</h2>
            <p class="muted">Una nota no se edita: se anula, y sus unidades vuelven
               a los lotes de los que salieron.</p>
        </header>

        <section class="card">
            <div class="field-row">
                <label class="field"><span>Desde</span>
                    <input type="date" id="from" value="${todayIso(-7)}"></label>
                <label class="field"><span>Hasta</span>
                    <input type="date" id="to" value="${todayIso()}"></label>
                <div class="field" style="align-self: end">
                    <button class="btn btn-secondary" id="reload">Buscar</button>
                </div>
            </div>
            <p class="muted small" id="summary"></p>

            <div class="table-scroll">
                <table class="data-table">
                    <thead>
                        <tr><th>Nota</th><th>Fecha</th><th>Cliente</th><th>Pago</th>
                            <th class="num">Líneas</th><th class="num">Total</th>
                            <th class="num">Margen</th><th></th></tr>
                    </thead>
                    <tbody id="sales-body"></tbody>
                </table>
            </div>
        </section>

        <section class="card" id="detail" hidden>
            <h3 id="detail-title">Nota</h3>
            <div class="ticket-preview"><iframe id="preview" title="Vista de la nota"></iframe></div>
        </section>`;

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
            frame.srcdoc = ticketHtml(note, settings, settings.ticket_width);
            host.querySelector('#detail').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            return;
        }

        if (event.target.classList.contains('print')) {
            printTicket(await BillingService.getSale(saleId), settings, settings.ticket_width);
            return;
        }

        if (event.target.classList.contains('cancel')) {
            // Anular devuelve stock: se pregunta una vez, con el número a la
            // vista, porque después no hay vuelta atrás.
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
