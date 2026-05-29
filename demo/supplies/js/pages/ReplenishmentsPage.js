/**
 * Replenishments page.
 *
 * Two tabs:
 *   - Sugeridas: items at/below the configured minimum, with checkbox
 *     multi-select to launch a bulk replenishment order in one round trip.
 *   - Listado: existing replenishments, filterable by status, with a
 *     detail modal that hosts the reception flow.
 *
 * Both tabs are restricted to ADMIN / WAREHOUSE_MANAGER (gated upstream by
 * the router and the nav).
 */
import {
    clear,
    closeModal,
    el,
    formatDate,
    formatNumber,
    openModal,
    showToast,
    statusBadge,
} from '../ui.js';

const STATUS_OPTIONS = [
    { value: '', label: 'Todos' },
    { value: 'REQUESTED', label: 'Pendientes' },
    { value: 'IN_RECEPTION', label: 'En recepción' },
    { value: 'COMPLETED', label: 'Completadas' },
    { value: 'CANCELLED', label: 'Anuladas' },
];

const TABS = [
    { key: 'pending', label: 'Sugeridas' },
    { key: 'list', label: 'Listado' },
];

export async function mountReplenishments({ host, actions, api }) {
    clear(host);
    actions.innerHTML = '';

    const tabsEl = el('div', { class: 'sup-tabs' });
    const panelEl = el('div', {});
    host.appendChild(tabsEl);
    host.appendChild(panelEl);

    const state = { api, actions, host: panelEl, statusFilter: '' };

    TABS.forEach(tab => {
        tabsEl.appendChild(el('button', {
            class: 'sup-tab', text: tab.label, dataset: { tab: tab.key },
            onClick: () => _activate(tab.key),
        }));
    });

    function _activate(key) {
        tabsEl.querySelectorAll('.sup-tab').forEach(b => {
            b.classList.toggle('active', b.dataset.tab === key);
        });
        if (key === 'pending') return _renderPending(state);
        return _renderList(state);
    }

    _activate('pending');
}

// --------------------------------------------------------------------- //
// PENDING                                                                //
// --------------------------------------------------------------------- //
async function _renderPending(state) {
    state.actions.innerHTML = '';
    clear(state.host);
    state.host.appendChild(el('p', { class: 'sup-placeholder', text: 'Calculando sugerencias…' }));

    try {
        const suggestions = await state.api.listPendingReplenishments();
        clear(state.host);
        if (suggestions.length === 0) {
            state.host.appendChild(el('div', {
                class: 'sup-card sup-card-padded sup-muted',
                text: 'No hay ítems bajo el mínimo configurado.',
            }));
            return;
        }
        const selection = new Map(); // item_id -> { qty, supplier_hint, notes, item }
        const tbody = el('tbody', {}, suggestions.map(s => {
            const checkbox = el('input', { type: 'checkbox' });
            const qtyInput = el('input', {
                type: 'number', step: '0.01', min: '0.01', value: s.suggested_qty,
            });
            const supplierInput = el('input', { type: 'text', placeholder: 'Proveedor (opc.)' });
            checkbox.onchange = () => {
                if (checkbox.checked) {
                    selection.set(s.item_id, {
                        item: s, qty: Number(qtyInput.value),
                        supplier_hint: supplierInput.value || null,
                    });
                } else {
                    selection.delete(s.item_id);
                }
            };
            [qtyInput, supplierInput].forEach(input => {
                input.onchange = () => {
                    if (!selection.has(s.item_id)) return;
                    selection.set(s.item_id, {
                        ...selection.get(s.item_id),
                        qty: Number(qtyInput.value),
                        supplier_hint: supplierInput.value || null,
                    });
                };
            });
            return el('tr', {}, [
                el('td', {}, [checkbox]),
                el('td', { text: s.item_code }),
                el('td', { text: s.item_name }),
                el('td', { text: formatNumber(s.current_stock) }),
                el('td', { text: formatNumber(s.min_stock) }),
                el('td', {}, [qtyInput]),
                el('td', {}, [supplierInput]),
            ]);
        }));

        const submitBtn = el('button', {
            class: 'sup-btn sup-btn-primary',
            html: '<i class="fa-solid fa-paper-plane"></i> Generar reposiciones',
            onClick: async () => {
                if (selection.size === 0) {
                    showToast('Selecciona al menos un ítem.', 'warning');
                    return;
                }
                const items = Array.from(selection.values()).map(s => ({
                    item_id: s.item.item_id,
                    requested_qty: s.qty,
                    supplier_hint: s.supplier_hint || null,
                    notes: null,
                }));
                try {
                    await state.api.createReplenishmentsBulk(items);
                    showToast(`${items.length} reposiciones creadas`, 'success');
                    _renderPending(state);
                } catch (err) {
                    showToast(err.message, 'error');
                }
            },
        });
        state.actions.appendChild(submitBtn);

        const thead = el('thead', {}, [el('tr', {}, [
            el('th', { text: '' }),
            el('th', { text: 'Código' }),
            el('th', { text: 'Ítem' }),
            el('th', { text: 'Stock actual' }),
            el('th', { text: 'Mínimo' }),
            el('th', { text: 'Cantidad' }),
            el('th', { text: 'Proveedor' }),
        ])]);
        state.host.appendChild(el('div', { class: 'sup-table-wrap' }, [
            el('table', { class: 'sup-table' }, [thead, tbody]),
        ]));
    } catch (err) {
        clear(state.host);
        state.host.appendChild(el('p', { class: 'sup-form-error', text: err.message }));
    }
}

// --------------------------------------------------------------------- //
// LIST                                                                   //
// --------------------------------------------------------------------- //
async function _renderList(state) {
    state.actions.innerHTML = '';
    clear(state.host);
    const filtersEl = el('div', { class: 'sup-filters' });
    const tableHost = el('div', {});
    state.host.appendChild(filtersEl);
    state.host.appendChild(tableHost);

    const statusSel = el('select', { name: 'status' });
    STATUS_OPTIONS.forEach(o => {
        statusSel.appendChild(el('option', { value: o.value, text: o.label }));
    });
    statusSel.value = state.statusFilter;
    statusSel.onchange = () => { state.statusFilter = statusSel.value; _load(); };
    filtersEl.appendChild(el('label', { class: 'sup-field' }, [
        el('span', { text: 'Estado' }), statusSel,
    ]));

    async function _load() {
        clear(tableHost);
        tableHost.appendChild(el('p', { class: 'sup-placeholder', text: 'Cargando…' }));
        try {
            const params = state.statusFilter ? { status: state.statusFilter } : {};
            const rows = await state.api.listReplenishments(params);
            clear(tableHost);
            if (rows.length === 0) {
                tableHost.appendChild(el('div', { class: 'sup-empty', text: 'Sin reposiciones.' }));
                return;
            }
            const thead = el('thead', {}, [el('tr', {}, [
                el('th', { text: 'Código' }),
                el('th', { text: 'Item ID' }),
                el('th', { text: 'Solicitado' }),
                el('th', { text: 'Recibido' }),
                el('th', { text: 'Estado' }),
                el('th', { text: 'Creado' }),
                el('th', { text: '' }),
            ])]);
            const tbody = el('tbody', {}, rows.map(r =>
                el('tr', {}, [
                    el('td', { text: r.code }),
                    el('td', { text: `#${r.item_id}` }),
                    el('td', { text: formatNumber(r.requested_qty) }),
                    el('td', { text: formatNumber(r.received_qty) }),
                    el('td', {}, [statusBadge(r.status)]),
                    el('td', { text: formatDate(r.created_at, true) }),
                    el('td', { class: 'sup-row-actions' }, [
                        el('button', {
                            class: 'sup-icon-btn', title: 'Ver detalle',
                            html: '<i class="fa-solid fa-magnifying-glass"></i>',
                            onClick: () => _openReplenishmentDetail(state, r.id, _load),
                        }),
                    ]),
                ]),
            ));
            tableHost.appendChild(el('div', { class: 'sup-table-wrap' }, [
                el('table', { class: 'sup-table' }, [thead, tbody]),
            ]));
        } catch (err) {
            clear(tableHost);
            tableHost.appendChild(el('p', { class: 'sup-form-error', text: err.message }));
        }
    }

    _load();
}

// --------------------------------------------------------------------- //
// DETAIL + reception                                                     //
// --------------------------------------------------------------------- //
async function _openReplenishmentDetail(state, id, onChange) {
    openModal({ title: 'Cargando…', body: 'Cargando…' });
    try {
        const [rep, receptions] = await Promise.all([
            state.api.getReplenishment(id),
            state.api.listReceptions(id),
        ]);
        _renderReplenishmentDetail(state, rep, receptions, onChange);
    } catch (err) {
        openModal({
            title: 'Error',
            body: el('p', { class: 'sup-form-error', text: err.message }),
            footer: [
                el('button', { class: 'sup-btn sup-btn-ghost', text: 'Cerrar', onClick: closeModal }),
            ],
        });
    }
}

function _renderReplenishmentDetail(state, rep, receptions, onChange) {
    const meta = el('div', { class: 'sup-stack' }, [
        el('div', { class: 'sup-flex-between' }, [
            el('span', {}, [statusBadge(rep.status)]),
            el('span', { class: 'sup-muted', text: rep.code }),
        ]),
        el('p', { text: `Solicitado: ${formatNumber(rep.requested_qty)}` }),
        el('p', { text: `Recibido: ${formatNumber(rep.received_qty)}` }),
        rep.supplier_hint ? el('p', { class: 'sup-muted', text: `Proveedor sugerido: ${rep.supplier_hint}` }) : null,
        rep.notes ? el('p', { text: `Notas: ${rep.notes}` }) : null,
    ].filter(Boolean));

    const receptionsTable = receptions.length === 0
        ? el('div', { class: 'sup-empty', text: 'Sin recepciones registradas.' })
        : el('div', { class: 'sup-table-wrap' }, [
            el('table', { class: 'sup-table' }, [
                el('thead', {}, [el('tr', {}, [
                    el('th', { text: '#' }),
                    el('th', { text: 'Cantidad' }),
                    el('th', { text: 'Lote' }),
                    el('th', { text: 'Vencimiento' }),
                    el('th', { text: 'Proveedor' }),
                    el('th', { text: 'Factura' }),
                    el('th', { text: 'Recibido por' }),
                    el('th', { text: 'Fecha' }),
                ])]),
                el('tbody', {}, receptions.map(r => el('tr', {}, [
                    el('td', { text: r.id }),
                    el('td', { text: formatNumber(r.received_qty) }),
                    el('td', { text: r.batch_code || '—' }),
                    el('td', { text: r.expiration_date || '—' }),
                    el('td', { text: r.supplier_name }),
                    el('td', { text: r.invoice_number || '—' }),
                    el('td', { text: r.received_by }),
                    el('td', { text: formatDate(r.received_at, true) }),
                ]))),
            ]),
        ]);

    const body = el('div', { class: 'sup-stack' }, [
        meta,
        el('h4', { text: 'Recepciones' }),
        receptionsTable,
    ]);

    const footer = [];
    if (rep.status === 'REQUESTED' || rep.status === 'IN_RECEPTION') {
        footer.push(el('button', {
            class: 'sup-btn sup-btn-primary',
            html: '<i class="fa-solid fa-box-archive"></i> Registrar recepción',
            onClick: () => _openReceptionForm(state, rep, onChange),
        }));
    }
    if (rep.status === 'REQUESTED') {
        footer.push(el('button', {
            class: 'sup-btn sup-btn-ghost',
            html: '<i class="fa-solid fa-ban"></i> Anular',
            onClick: async () => {
                const reason = prompt('Motivo de la anulación (opcional):') || '';
                try {
                    await state.api.cancelReplenishment(rep.id, reason);
                    showToast('Reposición anulada', 'success');
                    closeModal();
                    onChange?.();
                } catch (err) { showToast(err.message, 'error'); }
            },
        }));
    }
    footer.push(el('button', { class: 'sup-btn sup-btn-ghost', text: 'Cerrar', onClick: closeModal }));

    openModal({ title: `Reposición ${rep.code}`, body, footer, wide: true });
}

function _openReceptionForm(state, rep, onChange) {
    const form = el('form', { class: 'sup-stack' }, [
        el('div', { class: 'sup-field-row' }, [
            _field('received_qty', 'Cantidad recibida', { type: 'number', step: '0.01', required: true }),
            _field('supplier_name', 'Proveedor', { required: true, value: rep.supplier_hint || '' }),
        ]),
        el('div', { class: 'sup-field-row' }, [
            _field('batch_code', 'Código de lote'),
            _field('expiration_date', 'Vencimiento', { type: 'date' }),
        ]),
        el('div', { class: 'sup-field-row' }, [
            _field('invoice_number', 'Nº factura'),
            _field('file_key', 'S3 key (opcional)',
                { placeholder: 'cms/receptions/xxx.pdf' }),
        ]),
        _field('notes', 'Notas', { textarea: true }),
    ]);
    const errEl = el('p', { class: 'sup-form-error', hidden: true });
    form.appendChild(errEl);

    const submit = el('button', {
        class: 'sup-btn sup-btn-primary', text: 'Registrar',
        onClick: async () => {
            errEl.hidden = true;
            const fd = new FormData(form);
            const payload = {
                received_qty: Number(fd.get('received_qty')),
                supplier_name: fd.get('supplier_name'),
                batch_code: fd.get('batch_code') || null,
                expiration_date: fd.get('expiration_date') || null,
                invoice_number: fd.get('invoice_number') || null,
                file_key: fd.get('file_key') || null,
                notes: fd.get('notes') || null,
            };
            try {
                await state.api.createReception(rep.id, payload);
                showToast('Recepción registrada y kárdex actualizado.', 'success');
                closeModal();
                onChange?.();
            } catch (err) {
                errEl.textContent = err.message;
                errEl.hidden = false;
            }
        },
    });

    openModal({
        title: `Nueva recepción — ${rep.code}`,
        body: form,
        footer: [
            el('button', { class: 'sup-btn sup-btn-ghost', text: 'Cancelar', onClick: closeModal }),
            submit,
        ],
        wide: true,
    });
}

function _field(name, label, { value, required, type = 'text', step, textarea, placeholder } = {}) {
    const wrap = el('label', { class: 'sup-field' }, [el('span', { text: label })]);
    const input = el(textarea ? 'textarea' : 'input', {
        name, value: value ?? '', required: required || null,
        type: textarea ? null : type, step, placeholder,
    });
    if (textarea) input.textContent = value ?? '';
    wrap.appendChild(input);
    return wrap;
}
