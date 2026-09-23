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
import { BillingService, errorText } from '../services/BillingService.js';
import { printTicket } from './TicketPrinter.js';
import { escapeHtml, money, notify, setBusy } from '../ui.js';

const PAYMENT_METHODS = [
    ['EFECTIVO', 'Efectivo'],
    ['QR', 'QR'],
    ['TARJETA', 'Tarjeta']
];

/** Lines being sold, keyed by SKU so the same product cannot enter twice. */
let basket = new Map();
let catalogue = [];
let settings = null;

function total() {
    let subtotal = 0;
    let discount = 0;
    for (const line of basket.values()) {
        subtotal += line.quantity * (line.product.sale_price || 0);
        discount += line.discount || 0;
    }
    return { subtotal, discount, total: Math.max(subtotal - discount, 0) };
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
    host.querySelector('#charge').disabled = basket.size === 0;
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
                document: host.querySelector('#buyer-document').value.trim() || null
            },
            payment_method: host.querySelector('#payment-method').value,
            notes: host.querySelector('#sale-notes').value.trim() || null,
            lines: [...basket.values()].map((line) => ({
                sku: line.product.sku,
                quantity: Number(line.quantity),
                discount: Number(line.discount || 0)
            }))
        });

        notify(`Nota ${sale.number} emitida por Bs ${money(sale.total)}.`, 'success');
        printTicket(sale, settings, settings.ticket_width);

        basket = new Map();
        host.querySelector('#buyer-name').value = '';
        host.querySelector('#buyer-document').value = '';
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
                    </select>
                </label>
                <label class="field">
                    <span>Cliente (opcional)</span>
                    <input type="text" id="buyer-name" placeholder="Nombre o razón social">
                </label>
                <label class="field">
                    <span>NIT / CI</span>
                    <input type="text" id="buyer-document" inputmode="numeric">
                </label>
                <label class="field">
                    <span>Nota</span>
                    <input type="text" id="sale-notes" maxlength="300">
                </label>

                <button class="btn btn-primary btn-block" id="charge" disabled>
                    Cobrar e imprimir
                </button>
                <p class="muted small">Documento interno del comercio. La factura
                   fiscal llega con la fase del SIAT.</p>
            </aside>
        </div>`;

    try {
        [settings, catalogue] = await Promise.all([
            BillingService.getSettings(),
            BillingService.listProducts({ only_active: true }).then((page) => page.items)
        ]);
    } catch (error) {
        host.innerHTML = `<div class="card empty-state">
            <h3>No se pudo abrir el mostrador</h3>
            <p>${escapeHtml(errorText(error, 'El servicio no respondió.'))}</p></div>`;
        return;
    }

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

    host.querySelector('#charge').addEventListener('click', () => charge(host));

    renderBasket(host);
    search.focus();
}
