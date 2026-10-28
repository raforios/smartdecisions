/**
 * CounterPage — the till.
 *
 * The screen a pharmacy spends its day on, so it is built around the keyboard
 * and the barcode reader: type or scan, Enter adds the line, and the total is
 * always on screen. Nothing here asks for a price — the price comes from the
 * batch that will actually leave, which is what the shelf label says.
 *
 * The note is printed from what the service answered, never from what the
 * screen had: if the backend allocated two batches at two prices, the paper
 * has to say so.
 */
import {
    BillingService,
    PAYMENT_LABELS,
    SALE_PAYMENT_METHODS,
    currentTillOrNull,
    errorText
} from '../services/BillingService.js';
import { printTicket } from './TicketPrinter.js';
import { escapeHtml, money, notify, setBusy } from '../ui.js';

/** Debit and credit stay apart for the reports; for the SIN both are card. */
const PAYMENT_METHODS = SALE_PAYMENT_METHODS.map((value) => [value, PAYMENT_LABELS[value]]);

/** The option that opens one amount per method instead of a single method. */
const COMBINED = 'COMBINED';

/** Lines being sold, keyed by SKU so the same product cannot enter twice. */
let basket = new Map();
let catalogue = [];
let settings = null;
/** The open, current till of whoever charges; without it nothing is sold. */
let tillReady = false;

function total() {
    let subtotal = 0;
    let discount = 0;
    for (const line of basket.values()) {
        subtotal += line.quantity * (line.product.sale_price || 0);
        discount += line.discount || 0;
    }
    return { subtotal, discount, total: Math.max(subtotal - discount, 0) };
}

/**
 * How the sale is being paid: the parts typed when payments are combined, or
 * the single method for the whole total.
 */
function paymentParts(host) {
    if (host.querySelector('#payment-method').value !== COMBINED) {
        return [{ method: host.querySelector('#payment-method').value, amount: total().total }];
    }
    return [...host.querySelectorAll('.payment-part')]
        .map((input) => ({ method: input.dataset.method, amount: Number(input.value) || 0 }))
        .filter((part) => part.amount > 0);
}

function renderBasket(host) {
    const body = host.querySelector('#basket-body');
    if (!basket.size) {
        body.innerHTML = `<tr class="empty"><td colspan="5">
            Escanea o busca un producto para empezar.</td></tr>`;
    } else {
        body.innerHTML = [...basket.values()].map((line) => `
            <tr data-sku="${escapeHtml(line.product.sku)}">
                <td>
                    <strong>${escapeHtml(line.product.description)}</strong>
                    <span class="muted">${escapeHtml(line.product.sku)}</span>
                </td>
                <td class="num">
                    <input type="number" class="qty" min="0.01" step="any"
                           value="${line.quantity}" aria-label="Cantidad">
                </td>
                <td class="num">${money(line.product.sale_price)}</td>
                <td class="num">
                    <input type="number" class="discount" min="0" step="any"
                           value="${line.discount || 0}" aria-label="Descuento"
                           ${settings?.discounts_enabled ? '' : 'disabled'}>
                </td>
                <td class="num">
                    ${money(line.quantity * (line.product.sale_price || 0) - (line.discount || 0))}
                    <button class="link-danger remove" title="Quitar">✕</button>
                </td>
            </tr>`).join('');
    }

    const sums = total();
    host.querySelector('#sum-subtotal').textContent = money(sums.subtotal);
    host.querySelector('#sum-discount').textContent = money(sums.discount);
    host.querySelector('#sum-total').textContent = money(sums.total);
    host.querySelector('#charge').disabled = basket.size === 0 || !tillReady;
    // The basket changed the total: what is left to assign changes with it.
    const parts = host.querySelector('#combined-payments');
    if (parts && !parts.hidden) {
        const paid = paymentParts(host).reduce((sum, part) => sum + part.amount, 0);
        host.querySelector('#payments-left').textContent =
            `Falta asignar Bs ${money(Math.max(sums.total - paid, 0))}`;
    }
}

/** Adds one unit of a SKU, or one more when it is already in the basket. */
function addToBasket(host, product) {
    if (!product.available_quantity) {
        notify(`${product.description} no tiene unidades en estantería.`, 'error');
        return;
    }
    const line = basket.get(product.sku);
    if (line) {
        line.quantity += 1;
    } else {
        basket.set(product.sku, { product, quantity: 1, discount: 0 });
    }
    renderBasket(host);
}

function renderResults(host, term) {
    const results = host.querySelector('#search-results');
    const needle = term.trim().toLowerCase();
    if (!needle) {
        results.innerHTML = '';
        results.hidden = true;
        return;
    }
    const matches = catalogue.filter((product) =>
        product.is_active && (
            product.sku.toLowerCase().includes(needle) ||
            product.description.toLowerCase().includes(needle) ||
            (product.barcode || '').toLowerCase().includes(needle)
        )).slice(0, 8);

    results.innerHTML = matches.length
        ? matches.map((product) => `
            <button class="result" data-sku="${escapeHtml(product.sku)}">
                <span class="result-name">${escapeHtml(product.description)}</span>
                <span class="muted">${escapeHtml(product.laboratory)}</span>
                <span class="result-stock ${product.available_quantity ? '' : 'out'}">
                    ${money(product.available_quantity, 0)} u.
                </span>
                <span class="result-price">${money(product.sale_price)}</span>
            </button>`).join('')
        : '<p class="muted result-empty">Sin resultados.</p>';
    results.hidden = false;
}

async function charge(host) {
    const done = setBusy(host.querySelector('#charge'), 'Cobrando…');
    try {
        const sale = await BillingService.issueSale({
            buyer: {
                name: host.querySelector('#buyer-name').value.trim() || null,
                document: host.querySelector('#buyer-document').value.trim() || null,
                document_type: Number(host.querySelector('#buyer-document-type').value) || null,
                email: host.querySelector('#buyer-email').value.trim() || null
            },
            ...(host.querySelector('#payment-method').value === COMBINED
                ? { payments: paymentParts(host) }
                : { payment_method: host.querySelector('#payment-method').value }),
            card_number: host.querySelector('#card-number').value.trim() || null,
            notes: host.querySelector('#sale-notes').value.trim() || null,
            lines: [...basket.values()].map((line) => ({
                sku: line.product.sku,
                quantity: Number(line.quantity),
                discount: Number(line.discount || 0)
            }))
        });

        notify(sale.invoice
            ? `Factura ${sale.invoice.number} emitida${sale.invoice.state === 'OFFLINE'
                ? ' fuera de línea' : ''} por Bs ${money(sale.total)}.`
            : `Nota ${sale.number} emitida por Bs ${money(sale.total)}.`, 'success');
        if (sale.invoice) await renderContingency(host);
        printTicket(sale, settings, settings.ticket_width);

        basket = new Map();
        host.querySelector('#buyer-name').value = '';
        host.querySelector('#buyer-document').value = '';
        host.querySelector('#buyer-email').value = '';
        host.querySelector('#card-number').value = '';
        host.querySelectorAll('.payment-part').forEach((input) => { input.value = ''; });
        host.querySelector('#sale-notes').value = '';
        catalogue = (await BillingService.listProducts({ only_active: true })).items;
        renderBasket(host);
    } catch (error) {
        notify(errorText(error, 'No se pudo emitir la nota.'), 'error');
    } finally {
        done();
    }
}

/**
 * The till status above the counter. Without a till opened today nothing is
 * charged: the button stays disabled and the warning says what to do.
 */
function renderTillBar(host, till) {
    const bar = host.querySelector('#till-bar');
    tillReady = Boolean(till) && !till.expired;
    if (!till) {
        bar.innerHTML = `<div class="card form-error">No tienes una caja abierta.
            Ábrela en <strong>Caja y egresos</strong> para empezar a vender.</div>`;
    } else if (till.expired) {
        bar.innerHTML = `<div class="card form-error">Tu caja del
            ${escapeHtml(till.business_day)} sigue abierta. Ciérrala en
            <strong>Caja y egresos</strong> para vender hoy.</div>`;
    } else {
        bar.innerHTML = `<p class="muted small">Caja abierta desde ${
            escapeHtml(till.opened_at.slice(11, 16))} · efectivo esperado Bs ${
            money(till.expected_cash)}</p>`;
    }
}

/**
 * The notice of a point of sale issuing offline. The till keeps selling; the
 * cashier only has to know that the invoices reach the SIN later.
 */
async function renderContingency(host) {
    const bar = host.querySelector('#siat-bar');
    try {
        const status = await BillingService.contingency();
        bar.innerHTML = status.offline ? `<div class="card form-error">
            Sin conexión con Impuestos desde las ${
                escapeHtml(status.contingency.started_at.slice(11, 16))}: las facturas se
            emiten fuera de línea (${status.contingency.pending_invoices} pendiente(s)) y se
            envían solas al SIN cuando vuelva la conexión.</div>` : '';
    } catch (error) {
        bar.innerHTML = '';
        notify(errorText(error, 'No se pudo leer el estado de la conexión con el SIN.'), 'error');
    }
}

/**
 * A buyer the shop already invoiced fills in by their NIT or CI. Only empty
 * fields are filled: what the cashier already typed is theirs to keep.
 */
async function fillKnownBuyer(host) {
    const document = host.querySelector('#buyer-document').value.trim();
    if (!document) return;
    let customer;
    try {
        customer = await BillingService.getCustomer(document);
    } catch (error) {
        // A new buyer is the normal case, not an error: the invoice adds them.
        if (error.code !== 'CUSTOMER_NOT_FOUND') {
            notify(errorText(error, 'No se pudo buscar el cliente.'), 'error');
        }
        return;
    }
    const fill = (id, value) => {
        const input = host.querySelector(id);
        if (!input.value && value) input.value = value;
    };
    fill('#buyer-name', customer.name);
    fill('#buyer-email', customer.email);
    if (customer.document_type) {
        host.querySelector('#buyer-document-type').value = String(customer.document_type);
    }
}

/**
 * What changes at the counter when the shop invoices: the document type,
 * taken from the SIN's catalogue, and the line saying what the paper is.
 */
async function renderInvoicing(host) {
    const invoicing = Boolean(settings?.invoicing_enabled);
    host.querySelector('#document-kind').textContent = invoicing
        ? 'Cada venta se envía al SIN como factura.'
        : 'Nota de venta interna: no es factura fiscal.';
    host.querySelector('#document-type-field').hidden = !invoicing;
    host.querySelector('#email-field').hidden = !invoicing;
    if (!invoicing) return;
    host.querySelector('#buyer-document').addEventListener('change',
                                                          () => fillKnownBuyer(host));
    await renderContingency(host);
    try {
        const { entries } = await BillingService.siatCatalog('IDENTITY_DOCUMENT_TYPES');
        host.querySelector('#buyer-document-type').innerHTML = entries.map((type) =>
            `<option value="${escapeHtml(type.code)}">${escapeHtml(type.description)}</option>`
        ).join('');
    } catch (error) {
        notify(errorText(error, 'No se pudieron leer los tipos de documento.'), 'error');
    }
}

/**
 * Paints the till and wires it.
 *
 * @param {HTMLElement} host Where the section is mounted.
 */
export async function mountCounter(host) {
    host.innerHTML = `
        <header class="page-head">
            <h2>Mostrador</h2>
            <p class="muted">El precio sale del lote que va a salir, y el lote que
               sale es el que vence antes.</p>
        </header>

        <div id="till-bar"></div>
        <div id="siat-bar"></div>

        <div class="counter">
            <section class="card">
                <label class="field">
                    <span>Buscar o escanear</span>
                    <input type="search" id="search" autocomplete="off"
                           placeholder="Código, descripción o código de barras">
                </label>
                <div class="results" id="search-results" hidden></div>

                <div class="table-scroll">
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>Producto</th>
                                <th class="num">Cantidad</th>
                                <th class="num">Precio</th>
                                <th class="num">Descuento</th>
                                <th class="num">Importe</th>
                            </tr>
                        </thead>
                        <tbody id="basket-body"></tbody>
                    </table>
                </div>
            </section>

            <aside class="card counter-side">
                <div class="totals">
                    <div><span>Subtotal</span><strong id="sum-subtotal">0,00</strong></div>
                    <div><span>Descuentos</span><strong id="sum-discount">0,00</strong></div>
                    <div class="grand"><span>Total Bs</span><strong id="sum-total">0,00</strong></div>
                </div>

                <label class="field">
                    <span>Forma de pago</span>
                    <select id="payment-method">
                        ${PAYMENT_METHODS.map(([value, label]) =>
                            `<option value="${value}">${label}</option>`).join('')}
                        <option value="${COMBINED}">Combinada…</option>
                    </select>
                </label>
                <!-- A sale may be paid in up to three ways; the parts must add
                     up to the total, and the SIN invoices the combination. -->
                <div id="combined-payments" hidden>
                    ${PAYMENT_METHODS.map(([value, label]) => `
                        <label class="field">
                            <span>${label}</span>
                            <input type="number" class="payment-part" data-method="${value}"
                                   min="0" step="0.01" inputmode="decimal" placeholder="0,00">
                        </label>`).join('')}
                    <p class="muted small" id="payments-left"></p>
                </div>
                <!-- The card number only appears when paying by card: the rule
                     forbids sending it in any other case. It is masked on the
                     server and never stored in full. -->
                <label class="field" id="card-field" hidden>
                    <span>Número de tarjeta</span>
                    <input type="text" id="card-number" inputmode="numeric" maxlength="30"
                           placeholder="Se guarda enmascarado">
                </label>
                <label class="field">
                    <span>Cliente (opcional)</span>
                    <input type="text" id="buyer-name" placeholder="Nombre o razón social">
                </label>
                <label class="field">
                    <span id="document-label">NIT / CI</span>
                    <input type="text" id="buyer-document" inputmode="numeric">
                </label>
                <!-- The invoice carries the type of the buyer's document, from
                     the SIN's catalogue; an internal note does not need it. -->
                <label class="field" id="document-type-field" hidden>
                    <span>Tipo de documento</span>
                    <select id="buyer-document-type"></select>
                </label>
                <label class="field" id="email-field" hidden>
                    <span>Correo (para enviar la factura)</span>
                    <input type="email" id="buyer-email" maxlength="254">
                </label>
                <label class="field">
                    <span>Nota</span>
                    <input type="text" id="sale-notes" maxlength="300">
                </label>

                <button class="btn btn-primary btn-block" id="charge" disabled>
                    Cobrar e imprimir
                </button>
                <p class="muted small" id="document-kind"></p>
            </aside>
        </div>`;

    let till = null;
    try {
        [settings, catalogue, till] = await Promise.all([
            BillingService.getSettings(),
            BillingService.listProducts({ only_active: true }).then((page) => page.items),
            currentTillOrNull()
        ]);
    } catch (error) {
        host.innerHTML = `<div class="card empty-state">
            <h3>No se pudo abrir el mostrador</h3>
            <p>${escapeHtml(errorText(error, 'El servicio no respondió.'))}</p></div>`;
        return;
    }

    renderTillBar(host, till);
    await renderInvoicing(host);

    const search = host.querySelector('#search');
    search.addEventListener('input', (event) => renderResults(host, event.target.value));
    search.addEventListener('keydown', (event) => {
        if (event.key !== 'Enter') return;
        event.preventDefault();
        // A barcode reader types the code and presses Enter: an exact match
        // goes straight into the basket without touching the mouse.
        const needle = search.value.trim().toLowerCase();
        const exact = catalogue.find((product) =>
            product.sku.toLowerCase() === needle ||
            (product.barcode || '').toLowerCase() === needle);
        const only = host.querySelectorAll('#search-results .result');
        const picked = exact || (only.length === 1
            ? catalogue.find((product) => product.sku === only[0].dataset.sku)
            : null);
        if (picked) {
            addToBasket(host, picked);
            search.value = '';
            renderResults(host, '');
        }
    });

    host.querySelector('#search-results').addEventListener('click', (event) => {
        const button = event.target.closest('.result');
        if (!button) return;
        addToBasket(host, catalogue.find((product) => product.sku === button.dataset.sku));
        search.value = '';
        renderResults(host, '');
        search.focus();
    });

    host.querySelector('#basket-body').addEventListener('input', (event) => {
        const row = event.target.closest('tr');
        const line = basket.get(row?.dataset.sku);
        if (!line) return;
        if (event.target.classList.contains('qty')) {
            line.quantity = Math.max(Number(event.target.value) || 0, 0);
        } else if (event.target.classList.contains('discount')) {
            line.discount = Math.max(Number(event.target.value) || 0, 0);
        }
        renderBasket(host);
    });

    host.querySelector('#basket-body').addEventListener('click', (event) => {
        if (!event.target.classList.contains('remove')) return;
        basket.delete(event.target.closest('tr').dataset.sku);
        renderBasket(host);
    });

    // The card field only exists while the payment is by card, and it is
    // cleared when the method changes: a number left on screen would have
    // travelled with a cash sale, which the rule rejects.
    const method = host.querySelector('#payment-method');
    const cardField = host.querySelector('#card-field');
    const cardInput = host.querySelector('#card-number');
    const syncCardField = () => {
        const isCard = paymentParts(host).some((part) => part.method.startsWith('TARJETA'));
        cardField.hidden = !isCard;
        if (!isCard) cardInput.value = '';
        const paid = paymentParts(host).reduce((sum, part) => sum + part.amount, 0);
        const combined = method.value === COMBINED;
        host.querySelector('#combined-payments').hidden = !combined;
        host.querySelector('#payments-left').textContent = combined
            ? `Falta asignar Bs ${money(Math.max(total().total - paid, 0))}` : '';
    };
    method.addEventListener('change', syncCardField);
    host.querySelectorAll('.payment-part').forEach((input) =>
        input.addEventListener('input', syncCardField));
    syncCardField();

    // With nominativity on, the document stops being optional, and the label
    // has to say so before the cashier charges.
    if (settings?.buyer_required || settings?.invoicing_enabled) {
        host.querySelector('#document-label').textContent = 'NIT / CI (obligatorio)';
        host.querySelector('#buyer-document').required = true;
    }

    host.querySelector('#charge').addEventListener('click', () => charge(host));

    renderBasket(host);
    search.focus();
}
