/**
 * CatalogPage — los SKU y sus lotes.
 *
 * El catálogo no guarda precio: el que se muestra es el del lote que va a
 * salir, y al desplegar un producto se ven todos sus lotes en el orden en que
 * se venderán, con su vencimiento y su costo. Ahí mismo se reprecia uno.
 */
import { BillingService, errorText } from '../services/BillingService.js';
import { escapeHtml, money, notify, setBusy, shortDate } from '../ui.js';

/** Un lote a menos de estos días pide acción antes de que sea tarde. */
const EXPIRY_WARNING_DAYS = 60;

let products = [];

function daysTo(isoDate) {
    if (!isoDate) return null;
    const target = new Date(`${isoDate}T00:00:00`);
    return Math.round((target - new Date().setHours(0, 0, 0, 0)) / 86400000);
}

function expiryChip(isoDate) {
    const days = daysTo(isoDate);
    if (days === null) return '<span class="chip chip-muted">sin fecha</span>';
    if (days < 0) return `<span class="chip chip-danger">vencido ${shortDate(isoDate)}</span>`;
    if (days <= EXPIRY_WARNING_DAYS) {
        return `<span class="chip chip-warn">${shortDate(isoDate)} · ${days} d</span>`;
    }
    return `<span class="chip">${shortDate(isoDate)}</span>`;
}

function rowHtml(product) {
    return `
        <tr class="product-row" data-sku="${escapeHtml(product.sku)}">
            <td>
                <button class="link-toggle" type="button">
                    <strong>${escapeHtml(product.description)}</strong>
                </button>
                <span class="muted">${escapeHtml(product.sku)} · ${
                    escapeHtml(product.laboratory)}</span>
            </td>
            <td class="num ${product.below_minimum ? 'warn' : ''}">
                ${money(product.available_quantity, 0)}
                ${product.below_minimum
                    ? `<span class="muted">mín. ${money(product.min_stock, 0)}</span>` : ''}
            </td>
            <td class="num">${money(product.sale_price)}</td>
            <td>${product.next_expiry ? expiryChip(product.next_expiry)
                                      : '<span class="muted">—</span>'}</td>
            <td>${product.is_active ? '' : '<span class="chip chip-muted">de baja</span>'}</td>
        </tr>
        <tr class="lots-row" hidden><td colspan="5"></td></tr>`;
}

function render(host, term) {
    const needle = term.trim().toLowerCase();
    const shown = products.filter((product) => !needle
        || product.sku.toLowerCase().includes(needle)
        || product.description.toLowerCase().includes(needle)
        || product.laboratory.toLowerCase().includes(needle));

    host.querySelector('#catalog-body').innerHTML = shown.length
        ? shown.map(rowHtml).join('')
        : '<tr class="empty"><td colspan="5">Sin resultados.</td></tr>';
    host.querySelector('#count').textContent =
        `${shown.length} de ${products.length} productos`;
}

async function showLots(host, sku, holder) {
    holder.innerHTML = '<p class="muted small">Cargando lotes…</p>';
    try {
        const lots = await BillingService.lots(sku, { only_available: false });
        holder.innerHTML = lots.items.length ? `
            <table class="data-table">
                <thead>
                    <tr><th>Lote</th><th>Vence</th><th class="num">Quedan</th>
                        <th class="num">Costo</th><th class="num">Precio</th><th></th></tr>
                </thead>
                <tbody>
                    ${lots.items.map((lot) => `
                        <tr data-lot="${escapeHtml(lot.lot_id)}">
                            <td>${lot.lot_code ? escapeHtml(lot.lot_code)
                                                : '<span class="muted">sin código</span>'}</td>
                            <td>${expiryChip(lot.expiry_date)}</td>
                            <td class="num ${lot.quantity_remaining ? '' : 'muted'}">
                                ${money(lot.quantity_remaining, 0)} de ${
                                    money(lot.quantity_received, 0)}</td>
                            <td class="num">${money(lot.unit_cost)}</td>
                            <td class="num">
                                <input type="number" class="price" min="0.01" step="any"
                                       value="${lot.sale_price}" aria-label="Precio">
                            </td>
                            <td><button class="btn btn-ghost btn-small reprice">Guardar</button></td>
                        </tr>`).join('')}
                </tbody>
            </table>
            <p class="muted small">El costo no se edita: es lo que se pagó, y
               reescribirlo cambiaría el margen de cada venta ya hecha.</p>`
            : '<p class="muted small">Este producto todavía no tiene lotes. Se crean al recibir una compra.</p>';
    } catch (error) {
        holder.innerHTML = `<p class="muted small">${
            escapeHtml(errorText(error, 'No se pudieron leer los lotes.'))}</p>`;
    }
}

/**
 * Pinta el catálogo y lo deja operable.
 *
 * @param {HTMLElement} host Dónde se monta la sección.
 */
export async function mountCatalog(host) {
    host.innerHTML = `
        <header class="page-head">
            <h2>Catálogo</h2>
            <p class="muted">El precio que se ve es el del lote que sale próximo:
               es lo que dice la etiqueta del estante.</p>
        </header>

        <section class="card">
            <div class="field-row">
                <label class="field" style="flex: 2 1 260px">
                    <span>Buscar</span>
                    <input type="search" id="filter" placeholder="Código, descripción o laboratorio">
                </label>
                <div class="field" style="align-self: end">
                    <button class="btn btn-primary" id="new">Nuevo producto</button>
                </div>
            </div>
            <p class="muted small" id="count"></p>

            <div class="table-scroll">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Producto</th><th class="num">Disponible</th>
                            <th class="num">Precio</th><th>Vence</th><th></th>
                        </tr>
                    </thead>
                    <tbody id="catalog-body"></tbody>
                </table>
            </div>
        </section>

        <section class="card" id="new-form" hidden>
            <h3>Nuevo producto</h3>
            <div class="field-row">
                <label class="field"><span>Código (SKU)</span>
                    <input type="text" id="sku" maxlength="40"></label>
                <label class="field" style="flex: 2 1 240px"><span>Descripción</span>
                    <input type="text" id="description" maxlength="300"></label>
            </div>
            <div class="field-row">
                <label class="field"><span>Laboratorio o proveedor</span>
                    <input type="text" id="laboratory" maxlength="150"></label>
                <label class="field"><span>Código de barras</span>
                    <input type="text" id="barcode" maxlength="60"></label>
                <label class="field"><span>Stock mínimo</span>
                    <input type="number" id="min_stock" min="0" step="any" value="0"></label>
            </div>
            <button class="btn btn-primary" id="create">Registrar</button>
            <button class="btn btn-ghost" id="cancel">Cancelar</button>
        </section>`;

    products = (await BillingService.listProducts()).items;
    render(host, '');

    host.querySelector('#filter').addEventListener('input',
        (event) => render(host, event.target.value));

    host.querySelector('#new').addEventListener('click', () => {
        host.querySelector('#new-form').hidden = false;
        host.querySelector('#sku').focus();
    });
    host.querySelector('#cancel').addEventListener('click', () => {
        host.querySelector('#new-form').hidden = true;
    });

    host.querySelector('#create').addEventListener('click', async (event) => {
        const field = (id) => host.querySelector(`#${id}`).value.trim();
        if (!field('sku') || !field('description') || !field('laboratory')) {
            notify('Código, descripción y laboratorio son obligatorios.', 'error');
            return;
        }
        const done = setBusy(event.currentTarget, 'Registrando…');
        try {
            await BillingService.createProduct({
                sku: field('sku'),
                description: field('description'),
                laboratory: field('laboratory'),
                barcode: field('barcode') || null,
                min_stock: Number(host.querySelector('#min_stock').value) || 0
            });
            notify(`${field('description')} registrado.`, 'success');
            await mountCatalog(host);
        } catch (error) {
            notify(errorText(error, 'No se pudo registrar.'), 'error');
        } finally {
            done();
        }
    });

    host.querySelector('#catalog-body').addEventListener('click', async (event) => {
        const toggle = event.target.closest('.link-toggle');
        if (toggle) {
            const row = toggle.closest('tr');
            const lots = row.nextElementSibling;
            lots.hidden = !lots.hidden;
            if (!lots.hidden && !lots.dataset.loaded) {
                await showLots(host, row.dataset.sku, lots.querySelector('td'));
                lots.dataset.loaded = '1';
            }
            return;
        }

        const button = event.target.closest('.reprice');
        if (!button) return;
        const lotRow = button.closest('tr');
        const sku = button.closest('.lots-row').previousElementSibling.dataset.sku;
        const price = Number(lotRow.querySelector('.price').value);
        if (!(price > 0)) {
            notify('El precio tiene que ser mayor que cero.', 'error');
            return;
        }
        const done = setBusy(button, '…');
        try {
            await BillingService.repriceLot(sku, lotRow.dataset.lot, price);
            notify('Precio actualizado.', 'success');
            products = (await BillingService.listProducts()).items;
            render(host, host.querySelector('#filter').value);
        } catch (error) {
            notify(errorText(error, 'No se pudo reprecio.'), 'error');
        } finally {
            done();
        }
    });
}
