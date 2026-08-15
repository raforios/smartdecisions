/**
 * Entries page (Notas de Ingreso).
 *
 * Replaces the old replenishment flow. A warehouse entry has a document
 * header (type, supplier, requirement / delivery note / invoice with their
 * dates, observations, discount) plus one or more item lines. Each line is a
 * PEPS/FIFO cost layer once saved, so the note also drives the valued kardex.
 *
 * Restricted to ADMIN / WAREHOUSE_MANAGER (gated upstream by router and nav).
 */
import { hasRole, ROLES } from '../auth.js';
import {
    clear,
    collapsible,
    closeModal,
    el,
    formatDate,
    formatMoney,
    formatNumber,
    itemPicker,
    openModal,
    showToast,
} from '../ui.js';

const ENTRY_TYPES = [
    { value: 'COMPRA', label: 'Compra' },
    { value: 'DONACION_TRANSFERENCIA', label: 'Donación y/o Transferencia' },
    { value: 'REINGRESO', label: 'Reingreso' },
];
const TYPE_LABEL = Object.fromEntries(ENTRY_TYPES.map(t => [t.value, t.label]));

export async function mountEntries({ host, actions, api }) {
    clear(host);
    actions.innerHTML = '';
    const state = { api, host, actions, items: null };

    if (hasRole(ROLES.ADMIN, ROLES.WAREHOUSE_MANAGER)) {
        actions.appendChild(el('button', {
            class: 'sup-btn sup-btn-primary',
            html: '<i class="fa-solid fa-plus"></i> Nueva Nota de Ingreso',
            onClick: () => _openEntryForm(state),
        }));
    }
    await _renderList(state);
}

async function _ensureItems(state) {
    if (!state.items) {
        state.items = await state.api.listItems({ limit: 500 });
    }
    return state.items;
}

async function _ensureUnits(state) {
    if (!state.units) {
        state.units = await state.api.listUnits({ limit: 500 });
    }
    return state.units;
}

async function _ensureSuppliers(state) {
    // Only active vendors: the backend rejects notes issued to a deactivated
    // one, so offering them here would only produce errors.
    if (!state.suppliers) {
        state.suppliers = await state.api.listSuppliers({ limit: 500, only_active: true });
    }
    return state.suppliers;
}

// --------------------------------------------------------------------- //
// LIST                                                                   //
// --------------------------------------------------------------------- //
async function _renderList(state) {
    clear(state.host);
    state.host.appendChild(el('p', { class: 'sup-placeholder', text: 'Cargando notas de ingreso…' }));
    try {
        const rows = await state.api.listEntries({ limit: 200 });
        clear(state.host);
        if (rows.length === 0) {
            state.host.appendChild(el('div', { class: 'sup-empty', text: 'Aún no hay notas de ingreso.' }));
            return;
        }
        const thead = el('thead', {}, [el('tr', {}, [
            _th('Código'), _th('Tipo'), _th('Proveedor'),
            _th('Descuento'), _th('Total'), _th('Fecha'), _th(''),
        ])]);
        const tbody = el('tbody', {}, rows.map(r => el('tr', {}, [
            _td(r.code),
            _td(TYPE_LABEL[r.entry_type] || r.entry_type),
            _td(r.supplier || '—'),
            _td(formatMoney(r.discount)),
            _td(formatMoney(r.total)),
            _td(formatDate(r.created_at, true)),
            el('td', { class: 'sup-row-actions' }, [
                el('button', {
                    class: 'sup-icon-btn', title: 'Ver detalle',
                    html: '<i class="fa-solid fa-magnifying-glass"></i>',
                    onClick: () => _openDetail(state, r.id),
                }),
            ]),
        ])));
        const box = collapsible({
            title: 'Notas de Ingreso',
            subtitle: `${rows.length} nota(s)`,
            stateKey: 'entries.list',
        });
        box.body.appendChild(el('div', { class: 'sup-table-wrap' }, [
            el('table', { class: 'sup-table' }, [thead, tbody]),
        ]));
        state.host.appendChild(box.section);
    } catch (err) {
        clear(state.host);
        state.host.appendChild(el('p', { class: 'sup-form-error', text: err.message }));
    }
}

// --------------------------------------------------------------------- //
// NEW ENTRY FORM                                                         //
// --------------------------------------------------------------------- //
async function _openEntryForm(state) {
    const [items, units, suppliers] = await Promise.all([
        _ensureItems(state), _ensureUnits(state), _ensureSuppliers(state),
    ]);
    const unitById = new Map(units.map(u => [u.id, u]));
    const _unitLabel = item => unitById.get(item.unit_id)?.abbreviation || '';

    const lines = []; // { item, quantity, unit_cost }

    // Header fields.
    const typeSel = el('select', { name: 'entry_type' });
    ENTRY_TYPES.forEach(t => typeSel.appendChild(el('option', { value: t.value, text: t.label })));

    // Registered vendors only: the free-text field is gone so every note
    // points at a supplier record with its NIT and contact data.
    const supplierSel = el('select', { name: 'supplier_id' }, [
        el('option', { value: '', text: suppliers.length
            ? '— Seleccionar proveedor —'
            : 'No hay proveedores registrados' }),
    ]);
    suppliers.forEach(s => supplierSel.appendChild(el('option', {
        value: s.id, text: `${s.name} — NIT ${s.nit}`,
    })));

    const header = el('div', { class: 'sup-stack' }, [
        _wrap('Tipo de ingreso', typeSel),
        _wrap('Proveedor', supplierSel),
        el('div', { class: 'sup-field-row' }, [
            _field('requirement_no', 'N° requerimiento/preventivo'),
            _field('requirement_date', 'Fecha requerimiento', { type: 'date' }),
        ]),
        el('div', { class: 'sup-field-row' }, [
            _field('delivery_note', 'Nota de entrega'),
            _field('delivery_note_date', 'Fecha nota de entrega', { type: 'date' }),
        ]),
        el('div', { class: 'sup-field-row' }, [
            _field('invoice_no', 'Factura'),
            _field('authorization', 'Autorización'),
            _field('invoice_date', 'Fecha factura', { type: 'date' }),
        ]),
        _field('observations', 'Observaciones', { textarea: true }),
    ]);

    // Item picker: searches code and description, unlike the previous
    // datalist which only matched the code.
    const picker = itemPicker({
        items,
        placeholder: 'Buscar artículo por código o descripción…',
    });
    const addBtn = el('button', {
        type: 'button', class: 'sup-btn sup-btn-ghost',
        html: '<i class="fa-solid fa-plus"></i> Agregar',
        onClick: () => {
            const item = picker.selected();
            if (!item) {
                showToast('Selecciona un artículo válido de la lista.', 'warning');
                return;
            }
            if (lines.some(l => l.item.id === item.id)) {
                showToast('El artículo ya está en la nota.', 'warning');
                return;
            }
            lines.push({ item, quantity: 1, unit_cost: 0 });
            picker.reset();
            _renderLines();
        },
    });

    const linesHost = el('div', { class: 'sup-table-wrap' });
    const totalsEl = el('div', { class: 'sup-flex-between sup-totals' });
    const discountInput = el('input', {
        type: 'number', step: '0.01', min: '0', value: '0', name: 'discount',
    });
    discountInput.oninput = _recalcTotals;

    function _recalcTotals() {
        const subtotal = lines.reduce((acc, l) => acc + Number(l.quantity) * Number(l.unit_cost), 0);
        const discount = Number(discountInput.value) || 0;
        clear(totalsEl);
        totalsEl.appendChild(el('div', { class: 'sup-stack' }, [
            _wrap('Descuento', discountInput),
        ]));
        totalsEl.appendChild(el('div', { class: 'sup-totals-box' }, [
            el('p', { text: `Subtotal: ${formatMoney(subtotal)}` }),
            el('p', { text: `Descuento: ${formatMoney(discount)}` }),
            el('p', { class: 'sup-total-strong', text: `Total: ${formatMoney(subtotal - discount)}` }),
        ]));
    }

    function _renderLines() {
        clear(linesHost);
        if (lines.length === 0) {
            linesHost.appendChild(el('div', { class: 'sup-empty', text: 'Agrega artículos a la nota.' }));
            _recalcTotals();
            return;
        }
        const thead = el('thead', {}, [el('tr', {}, [
            _th('Código'), _th('Unidad'), _th('Detalle'),
            _th('Cantidad'), _th('P. unitario'), _th('P. total'), _th(''),
        ])]);
        const tbody = el('tbody', {}, lines.map((line, idx) => {
            const qtyInput = el('input', {
                type: 'number', step: '0.01', min: '0.01', value: line.quantity,
            });
            const costInput = el('input', {
                type: 'number', step: '0.01', min: '0', value: line.unit_cost,
            });
            const totalCell = el('td', { text: formatMoney(line.quantity * line.unit_cost) });
            qtyInput.oninput = () => {
                line.quantity = Number(qtyInput.value) || 0;
                totalCell.textContent = formatMoney(line.quantity * line.unit_cost);
                _recalcTotals();
            };
            costInput.oninput = () => {
                line.unit_cost = Number(costInput.value) || 0;
                totalCell.textContent = formatMoney(line.quantity * line.unit_cost);
                _recalcTotals();
            };
            return el('tr', {}, [
                _td(line.item.code),
                _td(_unitLabel(line.item)),
                _td(line.item.name),
                el('td', {}, [qtyInput]),
                el('td', {}, [costInput]),
                totalCell,
                el('td', { class: 'sup-row-actions' }, [
                    el('button', {
                        class: 'sup-icon-btn', title: 'Quitar',
                        html: '<i class="fa-solid fa-xmark"></i>',
                        onClick: () => { lines.splice(idx, 1); _renderLines(); },
                    }),
                ]),
            ]);
        }));
        linesHost.appendChild(el('table', { class: 'sup-table' }, [thead, tbody]));
        _recalcTotals();
    }

    _renderLines();

    const errEl = el('p', { class: 'sup-form-error', hidden: true });
    const body = el('div', { class: 'sup-stack' }, [
        header,
        el('h4', { text: 'Artículos' }),
        el('div', { class: 'sup-flex' }, [_wrap('Artículo', picker.el), addBtn]),
        linesHost,
        totalsEl,
        errEl,
    ]);

    const submitBtn = el('button', {
        class: 'sup-btn sup-btn-primary',
        html: '<i class="fa-solid fa-floppy-disk"></i> Guardar',
        onClick: async () => {
            errEl.hidden = true;
            if (lines.length === 0) {
                errEl.textContent = 'Agrega al menos un artículo.';
                errEl.hidden = false;
                return;
            }
            const payload = {
                entry_type: typeSel.value,
                supplier_id: supplierSel.value ? Number(supplierSel.value) : null,
                requirement_no: _val(header, 'requirement_no'),
                requirement_date: _val(header, 'requirement_date'),
                delivery_note: _val(header, 'delivery_note'),
                delivery_note_date: _val(header, 'delivery_note_date'),
                invoice_no: _val(header, 'invoice_no'),
                authorization: _val(header, 'authorization'),
                invoice_date: _val(header, 'invoice_date'),
                observations: _val(header, 'observations'),
                discount: Number(discountInput.value) || 0,
                details: lines.map(l => ({
                    item_id: l.item.id,
                    quantity: Number(l.quantity),
                    unit_cost: Number(l.unit_cost),
                })),
            };
            try {
                await state.api.createEntry(payload);
                showToast('Nota de ingreso registrada y kárdex actualizado.', 'success');
                closeModal();
                _renderList(state);
            } catch (err) {
                errEl.textContent = err.message;
                errEl.hidden = false;
            }
        },
    });

    openModal({
        title: 'Nueva Nota de Ingreso',
        body,
        footer: [
            el('button', { class: 'sup-btn sup-btn-ghost', text: 'Cancelar', onClick: closeModal }),
            submitBtn,
        ],
        wide: true,
    });
}

// --------------------------------------------------------------------- //
// DETAIL (printable note)                                                //
// --------------------------------------------------------------------- //
async function _openDetail(state, id) {
    openModal({ title: 'Cargando…', body: 'Cargando…' });
    try {
        const entry = await state.api.getEntry(id);
        const meta = el('div', { class: 'sup-stack' }, [
            _line('Tipo de ingreso', TYPE_LABEL[entry.entry_type] || entry.entry_type),
            _line('Proveedor', entry.supplier),
            _line('N° requerimiento/preventivo', _withDate(entry.requirement_no, entry.requirement_date)),
            _line('Nota de entrega', _withDate(entry.delivery_note, entry.delivery_note_date)),
            _line('Factura / autorización', _invoiceLine(entry)),
            _line('Observaciones', entry.observations),
        ].filter(Boolean));

        const thead = el('thead', {}, [el('tr', {}, [
            _th('Nro'), _th('Código'), _th('Unidad'), _th('Detalle'),
            _th('Cantidad'), _th('P. unitario'), _th('P. total'),
        ])]);
        const tbody = el('tbody', {}, entry.details.map((d, i) => el('tr', {}, [
            _td(String(i + 1)),
            _td(d.item_code),
            _td(d.unit),
            _td(d.item_name),
            _td(formatNumber(d.qty_initial)),
            _td(formatMoney(d.unit_cost)),
            _td(formatMoney(d.total_cost)),
        ])));

        const body = el('div', { class: 'sup-stack' }, [
            meta,
            el('h4', { text: 'Detalle' }),
            el('div', { class: 'sup-table-wrap' }, [el('table', { class: 'sup-table' }, [thead, tbody])]),
            el('div', { class: 'sup-totals-box' }, [
                el('p', { text: `Subtotal: ${formatMoney(entry.subtotal)}` }),
                el('p', { text: `Descuento: ${formatMoney(entry.discount)}` }),
                el('p', { class: 'sup-total-strong', text: `Total: ${formatMoney(entry.total)}` }),
            ]),
        ]);

        openModal({
            title: `Nota de Ingreso ${entry.code}`,
            body,
            footer: [
                el('button', {
                    class: 'sup-btn sup-btn-ghost',
                    html: '<i class="fa-solid fa-print"></i> Imprimir',
                    onClick: () => window.print(),
                }),
                el('button', { class: 'sup-btn sup-btn-primary', text: 'Cerrar', onClick: closeModal }),
            ],
            wide: true,
        });
    } catch (err) {
        openModal({
            title: 'Error',
            body: el('p', { class: 'sup-form-error', text: err.message }),
            footer: [el('button', { class: 'sup-btn sup-btn-ghost', text: 'Cerrar', onClick: closeModal })],
        });
    }
}

// --------------------------------------------------------------------- //
// Helpers                                                                //
// --------------------------------------------------------------------- //
function _th(text) { return el('th', { text }); }
function _td(text) { return el('td', { text: text ?? '—' }); }

function _wrap(label, control) {
    return el('label', { class: 'sup-field' }, [el('span', { text: label }), control]);
}

function _field(name, label, { value, type = 'text', textarea, placeholder } = {}) {
    const wrap = el('label', { class: 'sup-field' }, [el('span', { text: label })]);
    const input = el(textarea ? 'textarea' : 'input', {
        name, value: value ?? '', type: textarea ? null : type, placeholder,
    });
    if (textarea) input.textContent = value ?? '';
    wrap.appendChild(input);
    return wrap;
}

function _val(scope, name) {
    const node = scope.querySelector(`[name="${name}"]`);
    const value = node ? node.value.trim() : '';
    return value === '' ? null : value;
}

function _line(label, value) {
    if (!value) return null;
    return el('p', {}, [el('strong', { text: `${label}: ` }), el('span', { text: value })]);
}

function _withDate(value, date) {
    if (!value) return null;
    // The API returns plain ISO dates here; the rest of the app shows dd/mm/aaaa.
    return date ? `${value} (${formatDate(date)})` : value;
}

function _invoiceLine(entry) {
    if (!entry.invoice_no && !entry.authorization) return null;
    const invoiceDate = entry.invoice_date ? formatDate(entry.invoice_date) : null;
    const parts = [entry.invoice_no, entry.authorization, invoiceDate].filter(Boolean);
    return parts.join(' · ');
}
