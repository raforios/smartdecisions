/**
 * CustomersPage — the buyers the merchant invoiced, by NIT or CI.
 *
 * The invoices write this list: a new document is added, a known one only gets
 * what it lacked. Correcting a customer is done here and only here, by whoever
 * runs the shop, because an invoice must never undo a correction.
 */
import { hasRole } from '../auth.js';
import { BillingService, errorText } from '../services/BillingService.js';
import { escapeHtml, notify, setBusy, stamp } from '../ui.js';

let customers = [];
/** The SIN's identity document types, by code. */
let documentTypes = new Map();

function rowHtml(customer, canEdit) {
    return `
        <tr data-document="${escapeHtml(customer.document)}">
            <td><strong>${escapeHtml(customer.document)}</strong></td>
            <td>${escapeHtml(documentTypes.get(String(customer.document_type))
                             || customer.document_type || '—')}</td>
            <td>${customer.name ? escapeHtml(customer.name) : '<span class="muted">—</span>'}</td>
            <td>${customer.email ? escapeHtml(customer.email) : '<span class="muted">—</span>'}</td>
            <td>${customer.last_invoiced_at ? stamp(customer.last_invoiced_at) : '—'}</td>
            <td>${canEdit ? '<button class="btn btn-ghost btn-small edit">Corregir</button>' : ''}</td>
        </tr>`;
}

function render(host) {
    const needle = host.querySelector('#filter').value.trim().toLowerCase();
    const canEdit = hasRole('ADMIN', 'MANAGER');
    const shown = customers.filter((customer) => !needle ||
        customer.document.toLowerCase().includes(needle) ||
        (customer.name || '').toLowerCase().includes(needle) ||
        (customer.email || '').toLowerCase().includes(needle));
    host.querySelector('#customers-body').innerHTML = shown.length
        ? shown.map((customer) => rowHtml(customer, canEdit)).join('')
        : '<tr class="empty"><td colspan="6">Todavía no hay clientes: se agregan solos al facturar.</td></tr>';
    host.querySelector('#summary').textContent = `${shown.length} de ${customers.length} cliente(s)`;
}

async function load(host) {
    try {
        customers = (await BillingService.listCustomers()).items;
        render(host);
    } catch (error) {
        host.querySelector('#customers-body').innerHTML = `<tr class="empty"><td colspan="6">${
            escapeHtml(errorText(error, 'No se pudieron leer los clientes.'))}</td></tr>`;
    }
}

function openEditor(host, document) {
    const customer = customers.find((one) => one.document === document);
    const panel = host.querySelector('#editor');
    panel.dataset.document = document;
    host.querySelector('#editor-title').textContent = `Corregir cliente ${document}`;
    host.querySelector('#edit-name').value = customer.name || '';
    host.querySelector('#edit-email').value = customer.email || '';
    host.querySelector('#edit-type').innerHTML = [...documentTypes].map(([code, label]) =>
        `<option value="${escapeHtml(code)}"
            ${String(customer.document_type) === code ? 'selected' : ''}>${escapeHtml(label)}</option>`
    ).join('');
    panel.hidden = false;
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function wireEditor(host) {
    const panel = host.querySelector('#editor');
    host.querySelector('#edit-back').addEventListener('click', () => { panel.hidden = true; });
    host.querySelector('#edit-save').addEventListener('click', async (event) => {
        const done = setBusy(event.currentTarget, 'Guardando…');
        try {
            await BillingService.updateCustomer(panel.dataset.document, {
                name: host.querySelector('#edit-name').value.trim() || null,
                email: host.querySelector('#edit-email').value.trim() || null,
                document_type: Number(host.querySelector('#edit-type').value) || null
            });
            notify('Cliente corregido.', 'success');
            panel.hidden = true;
            await load(host);
        } catch (error) {
            notify(errorText(error, 'No se pudo corregir el cliente.'), 'error');
        } finally {
            done();
        }
    });
}

/**
 * Paints the customers and wires their correction.
 *
 * @param {HTMLElement} host Where the section mounts.
 */
export async function mountCustomers(host) {
    host.innerHTML = `
        <header class="page-head">
            <h2>Clientes</h2>
            <p class="muted">Los compradores a los que facturaste. Se agregan solos
               al facturar; un dato mal escrito se corrige aquí.</p>
        </header>

        <section class="card">
            <label class="field">
                <span>Buscar</span>
                <input type="search" id="filter" placeholder="NIT o CI, nombre o correo">
            </label>
            <p class="muted small" id="summary"></p>
            <div class="table-scroll">
                <table class="data-table">
                    <thead>
                        <tr><th>NIT / CI</th><th>Tipo</th><th>Nombre</th><th>Correo</th>
                            <th>Última factura</th><th></th></tr>
                    </thead>
                    <tbody id="customers-body"></tbody>
                </table>
            </div>
        </section>

        <section class="card" id="editor" hidden>
            <h3 id="editor-title">Corregir cliente</h3>
            <label class="field"><span>Nombre o razón social</span>
                <input type="text" id="edit-name" maxlength="200"></label>
            <label class="field"><span>Tipo de documento</span>
                <select id="edit-type"></select></label>
            <label class="field"><span>Correo para enviar la factura</span>
                <input type="email" id="edit-email" maxlength="254"></label>
            <div class="form-actions">
                <button class="btn btn-primary" id="edit-save" type="button">Guardar</button>
                <button class="btn btn-ghost" id="edit-back" type="button">Volver</button>
            </div>
        </section>`;

    try {
        const { entries } = await BillingService.siatCatalog('IDENTITY_DOCUMENT_TYPES');
        documentTypes = new Map(entries.map((type) => [String(type.code), type.description]));
    } catch (error) {
        // Without the catalogue the list still shows the codes; only the
        // names of the document types are missing.
        if (error.code !== 'CATALOG_NOT_SYNCED') {
            notify(errorText(error, 'No se pudieron leer los tipos de documento.'), 'error');
        }
    }

    wireEditor(host);
    host.querySelector('#filter').addEventListener('input', () => render(host));
    host.querySelector('#customers-body').addEventListener('click', (event) => {
        const row = event.target.closest('tr[data-document]');
        if (row && event.target.classList.contains('edit')) openEditor(host, row.dataset.document);
    });
    await load(host);
}
