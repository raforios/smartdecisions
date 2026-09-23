/**
 * PurchasesPage — la nota de compra o recepción.
 *
 * Cada línea crea un lote, y el lote es el que lleva el costo, el precio y el
 * vencimiento. Por eso el formulario pide las cuatro cosas juntas: cargarlas
 * después significaría vender a un precio que nadie fijó.
 */
import { BillingService, errorText } from '../services/BillingService.js';
import { escapeHtml, money, notify, setBusy, shortDate, stamp, todayIso } from '../ui.js';

let catalogue = [];
let lines = [];

function renderLines(host) {
    const body = host.querySelector('#lines-body');
    body.innerHTML = lines.length ? lines.map((line, index) => `
        <tr data-index="${index}">
            <td>
                <strong>${escapeHtml(line.description)}</strong>
                <span class="muted">${escapeHtml(line.sku)}</span>
            </td>
            <td class="num">${money(line.quantity, 0)}</td>
            <td class="num">${money(line.unit_cost)}</td>
            <td class="num">${money(line.sale_price)}</td>
            <td>${line.lot_code ? escapeHtml(line.lot_code) : '<span class="muted">—</span>'}</td>
            <td>${line.expiry_date ? shortDate(line.expiry_date)
                                   : '<span class="muted">sin fecha</span>'}</td>
            <td class="num">${money(line.quantity * line.unit_cost)}
                <button class="link-danger remove" title="Quitar">✕</button></td>
        </tr>`).join('')
        : '<tr class="empty"><td colspan="7">Agrega los productos que llegaron.</td></tr>';

    const total = lines.reduce((sum, line) => sum + line.quantity * line.unit_cost, 0);
    host.querySelector('#total-cost').textContent = money(total);
    host.querySelector('#save').disabled = lines.length === 0;
}

async function renderHistory(host) {
    const holder = host.querySelector('#history');
    try {
        const page = await BillingService.listPurchases({
            date_from: todayIso(-30), date_to: todayIso()
        });
        holder.innerHTML = page.items.length ? `
            <table class="data-table">
                <thead><tr><th>Nota</th><th>Proveedor</th><th>Fecha</th>
                           <th class="num">Líneas</th><th class="num">Costo</th></tr></thead>
                <tbody>
                    ${page.items.map((note) => `
                        <tr>
                            <td><strong>${escapeHtml(note.number)}</strong>
                                ${note.invoice_number
                                    ? `<span class="muted">fact. ${
                                        escapeHtml(note.invoice_number)}</span>` : ''}</td>
                            <td>${escapeHtml(note.supplier_name)}</td>
                            <td>${stamp(note.created_at)}</td>
                            <td class="num">${note.lines.length}</td>
                            <td class="num">${money(note.total_cost)}</td>
                        </tr>`).join('')}
                </tbody>
            </table>`
            : '<p class="muted small">No hubo recepciones en los últimos 30 días.</p>';
    } catch (error) {
        holder.innerHTML = `<p class="muted small">${
            escapeHtml(errorText(error, 'No se pudo leer el historial.'))}</p>`;
    }
}

/**
 * Pinta la recepción y la deja operable.
 *
 * @param {HTMLElement} host Dónde se monta la sección.
 */
export async function mountPurchases(host) {
    lines = [];
    host.innerHTML = `
        <header class="page-head">
            <h2>Recepción</h2>
            <p class="muted">Lo que entregó el laboratorio o la droguería. Cada línea
               se convierte en un lote con su costo, su precio y su vencimiento.</p>
        </header>

        <section class="card">
            <h3>Datos de la entrega</h3>
            <div class="field-row">
                <label class="field" style="flex: 2 1 240px"><span>Proveedor</span>
                    <input type="text" id="supplier_name" maxlength="200"></label>
                <label class="field"><span>NIT</span>
                    <input type="text" id="supplier_document" maxlength="40"></label>
                <label class="field"><span>N.º de factura</span>
                    <input type="text" id="invoice_number" maxlength="60"></label>
                <label class="field"><span>Fecha de factura</span>
                    <input type="date" id="invoice_date"></label>
            </div>
        </section>

        <section class="card">
            <h3>Productos recibidos</h3>
            <div class="field-row">
                <label class="field" style="flex: 2 1 240px"><span>Producto</span>
                    <select id="sku"></select></label>
                <label class="field"><span>Cantidad</span>
                    <input type="number" id="quantity" min="0.01" step="any"></label>
                <label class="field"><span>Costo unitario</span>
                    <input type="number" id="unit_cost" min="0" step="any"></label>
                <label class="field"><span>Precio de venta</span>
                    <input type="number" id="sale_price" min="0.01" step="any"></label>
                <label class="field"><span>Lote</span>
                    <input type="text" id="lot_code" maxlength="60"></label>
                <label class="field"><span>Vence</span>
                    <input type="date" id="expiry_date"></label>
                <div class="field" style="align-self: end">
                    <button class="btn btn-secondary" id="add">Agregar</button>
                </div>
            </div>

            <div class="table-scroll">
                <table class="data-table">
                    <thead>
                        <tr><th>Producto</th><th class="num">Cantidad</th>
                            <th class="num">Costo</th><th class="num">Precio</th>
                            <th>Lote</th><th>Vence</th><th class="num">Importe</th></tr>
                    </thead>
                    <tbody id="lines-body"></tbody>
                </table>
            </div>

            <div class="totals" style="margin-top: 1rem">
                <div class="grand"><span>Costo total Bs</span><strong id="total-cost">0,00</strong></div>
            </div>
            <button class="btn btn-primary" id="save" disabled>Registrar recepción</button>
        </section>

        <section class="card">
            <h3>Últimas recepciones</h3>
            <div id="history"><p class="muted small">Cargando…</p></div>
        </section>`;

    catalogue = (await BillingService.listProducts({ only_active: true })).items;
    host.querySelector('#sku').innerHTML = catalogue.length
        ? catalogue.map((product) => `<option value="${escapeHtml(product.sku)}">${
            escapeHtml(product.description)} — ${escapeHtml(product.sku)}</option>`).join('')
        : '<option value="">Registra un producto primero</option>';

    renderLines(host);
    await renderHistory(host);

    host.querySelector('#add').addEventListener('click', () => {
        const sku = host.querySelector('#sku').value;
        const product = catalogue.find((one) => one.sku === sku);
        const quantity = Number(host.querySelector('#quantity').value);
        const unitCost = Number(host.querySelector('#unit_cost').value);
        const salePrice = Number(host.querySelector('#sale_price').value);

        if (!product || !(quantity > 0) || !(salePrice > 0) || unitCost < 0) {
            notify('Faltan cantidad, costo o precio de venta.', 'error');
            return;
        }
        lines.push({
            sku, description: product.description, quantity,
            unit_cost: unitCost, sale_price: salePrice,
            lot_code: host.querySelector('#lot_code').value.trim() || null,
            expiry_date: host.querySelector('#expiry_date').value || null
        });
        ['quantity', 'unit_cost', 'sale_price', 'lot_code', 'expiry_date']
            .forEach((id) => { host.querySelector(`#${id}`).value = ''; });
        renderLines(host);
    });

    host.querySelector('#lines-body').addEventListener('click', (event) => {
        if (!event.target.classList.contains('remove')) return;
        lines.splice(Number(event.target.closest('tr').dataset.index), 1);
        renderLines(host);
    });

    host.querySelector('#save').addEventListener('click', async (event) => {
        const supplier = host.querySelector('#supplier_name').value.trim();
        if (!supplier) {
            notify('El proveedor es obligatorio.', 'error');
            return;
        }
        const done = setBusy(event.currentTarget, 'Registrando…');
        try {
            const note = await BillingService.receivePurchase({
                supplier_name: supplier,
                supplier_document: host.querySelector('#supplier_document').value.trim() || null,
                invoice_number: host.querySelector('#invoice_number').value.trim() || null,
                invoice_date: host.querySelector('#invoice_date').value || null,
                lines: lines.map(({ description, ...line }) => line)
            });
            notify(`Recepción ${note.number} registrada: ${note.lines.length} lote(s).`, 'success');
            await mountPurchases(host);
        } catch (error) {
            notify(errorText(error, 'No se pudo registrar la recepción.'), 'error');
        } finally {
            done();
        }
    });
}
