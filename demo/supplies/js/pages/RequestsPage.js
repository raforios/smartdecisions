/**
 * Requests page.
 *
 * Covers both flows of the supply request lifecycle:
 *   - REQUESTER: creates a request, deletes own CREATED requests, closes a
 *     DELIVERED request (conformity).
 *   - WAREHOUSE_MANAGER / ADMIN: processes, delivers, rejects and cancels.
 *
 * The list is filterable; clicking a row opens a detail modal that also
 * hosts every transition button — visibility depends on the user's role and
 * the request's current status.
 */
import { hasRole, ROLES } from '../auth.js';
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
import { openRequestDetailModal } from './RequestDetailModal.js';

const STATUS_OPTIONS = [
    { value: '', label: 'Todos' },
    { value: 'CREATED', label: 'Creada' },
    { value: 'IN_PROCESS', label: 'En proceso' },
    { value: 'DELIVERED', label: 'Entregada' },
    { value: 'CLOSED', label: 'Cerrada' },
    { value: 'REJECTED', label: 'Rechazada' },
    { value: 'CANCELLED', label: 'Anulada' },
];

export async function mountRequests({ host, actions, api }) {
    clear(host);
    actions.innerHTML = '';

    actions.appendChild(el('button', {
        class: 'sup-btn sup-btn-primary',
        html: '<i class="fa-solid fa-plus"></i> Nueva solicitud',
        onClick: () => _openCreateModal(api, () => _refresh(state)),
    }));

    const filtersEl = el('div', { class: 'sup-filters' });
    const tableHost = el('div', {});
    host.appendChild(filtersEl);
    host.appendChild(tableHost);

    const state = {
        api,
        tableHost,
        filters: { status: '', requester_email: '', date_from: '', date_to: '' },
    };

    _renderFilters(filtersEl, state);
    await _refresh(state);
}

function _renderFilters(filtersEl, state) {
    filtersEl.innerHTML = '';

    const statusSel = el('select', { name: 'status' });
    STATUS_OPTIONS.forEach(o => {
        statusSel.appendChild(el('option', { value: o.value, text: o.label }));
    });
    statusSel.value = state.filters.status;
    statusSel.onchange = () => { state.filters.status = statusSel.value; _refresh(state); };

    const statusField = el('label', { class: 'sup-field' }, [
        el('span', { text: 'Estado' }), statusSel,
    ]);
    filtersEl.appendChild(statusField);

    if (!hasRole(ROLES.REQUESTER) || hasRole(ROLES.ADMIN) || hasRole(ROLES.WAREHOUSE_MANAGER)) {
        const emailIn = el('input', {
            type: 'email', name: 'requester_email', placeholder: 'usuario@...',
            value: state.filters.requester_email,
        });
        emailIn.onchange = () => {
            state.filters.requester_email = emailIn.value;
            _refresh(state);
        };
        filtersEl.appendChild(el('label', { class: 'sup-field' }, [
            el('span', { text: 'Solicitante' }), emailIn,
        ]));
    }

    const dateFrom = el('input', { type: 'date', name: 'date_from', value: state.filters.date_from });
    dateFrom.onchange = () => { state.filters.date_from = dateFrom.value; _refresh(state); };
    filtersEl.appendChild(el('label', { class: 'sup-field' }, [
        el('span', { text: 'Desde' }), dateFrom,
    ]));

    const dateTo = el('input', { type: 'date', name: 'date_to', value: state.filters.date_to });
    dateTo.onchange = () => { state.filters.date_to = dateTo.value; _refresh(state); };
    filtersEl.appendChild(el('label', { class: 'sup-field' }, [
        el('span', { text: 'Hasta' }), dateTo,
    ]));

    filtersEl.appendChild(el('button', {
        class: 'sup-btn sup-btn-ghost',
        text: 'Limpiar',
        onClick: () => {
            state.filters = { status: '', requester_email: '', date_from: '', date_to: '' };
            _renderFilters(filtersEl, state);
            _refresh(state);
        },
    }));
}

async function _refresh(state) {
    clear(state.tableHost);
    state.tableHost.appendChild(el('p', { class: 'sup-placeholder', text: 'Cargando…' }));
    try {
        const { date_from, date_to, ...rest } = state.filters;
        const params = { ...rest };
        if (date_from) params.date_from = `${date_from}T00:00:00`;
        if (date_to) params.date_to = `${date_to}T23:59:59`;
        const rows = await state.api.listRequests(params);
        clear(state.tableHost);
        state.tableHost.appendChild(_renderTable(state, rows));
    } catch (err) {
        clear(state.tableHost);
        state.tableHost.appendChild(el('p', { class: 'sup-form-error', text: err.message }));
    }
}

function _renderTable(state, rows) {
    if (rows.length === 0) {
        return el('div', { class: 'sup-empty', text: 'Sin solicitudes.' });
    }
    const thead = el('thead', {}, [el('tr', {}, [
        el('th', { text: 'Código' }),
        el('th', { text: 'Solicitante' }),
        el('th', { text: 'Estado' }),
        el('th', { text: 'Solicitado' }),
        el('th', { text: 'Procesado' }),
        el('th', { text: 'Cerrado' }),
        el('th', { text: '' }),
    ])]);
    const tbody = el('tbody', {}, rows.map(row =>
        el('tr', { dataset: { id: row.id } }, [
            el('td', { text: row.code }),
            el('td', { text: row.requester_email }),
            el('td', {}, [statusBadge(row.status)]),
            el('td', { text: formatDate(row.requested_at, true) }),
            el('td', { text: row.processed_at ? formatDate(row.processed_at, true) : '—' }),
            el('td', { text: row.closed_at ? formatDate(row.closed_at, true) : '—' }),
            el('td', { class: 'sup-row-actions' }, [
                el('button', {
                    class: 'sup-icon-btn', title: 'Ver detalle',
                    html: '<i class="fa-solid fa-magnifying-glass"></i>',
                    onClick: () => openRequestDetailModal({
                        api: state.api,
                        requestId: row.id,
                        onChange: () => _refresh(state),
                    }),
                }),
            ]),
        ]),
    ));
    return el('div', { class: 'sup-table-wrap' }, [
        el('table', { class: 'sup-table' }, [thead, tbody]),
    ]);
}

// --------------------------------------------------------------------- //
// CREATE modal                                                           //
// --------------------------------------------------------------------- //
async function _openCreateModal(api, onSuccess) {
    let availableItems = [];
    try {
        availableItems = await api.listItems({ only_available: true, limit: 500 });
    } catch (err) {
        showToast(`No se pudieron cargar los ítems: ${err.message}`, 'error');
        return;
    }
    if (availableItems.length === 0) {
        showToast('No hay ítems disponibles arriba del mínimo.', 'warning');
        return;
    }

    const lines = []; // { item_id, requested_qty }
    const linesHost = el('div', { class: 'sup-stack' });
    const errEl = el('p', { class: 'sup-form-error', hidden: true });

    const itemPicker = (() => {
        const select = el('select', { name: 'item_id' });
        select.appendChild(el('option', { value: '', text: '— Elegir ítem —' }));
        availableItems.forEach(it => {
            select.appendChild(el('option', {
                value: it.id,
                text: `${it.code} — ${it.name} (disponible ${formatNumber(
                    Number(it.current_stock) - Number(it.min_stock))})`,
            }));
        });
        return select;
    })();

    const qtyInput = el('input', { type: 'number', step: '0.01', min: '0.01', name: 'qty' });

    const addBtn = el('button', {
        class: 'sup-btn sup-btn-ghost',
        type: 'button',
        text: 'Agregar línea',
        onClick: () => {
            const item = availableItems.find(i => Number(i.id) === Number(itemPicker.value));
            const qty = Number(qtyInput.value);
            if (!item || !qty || qty <= 0) {
                errEl.textContent = 'Selecciona ítem y cantidad mayor a cero.';
                errEl.hidden = false;
                return;
            }
            errEl.hidden = true;
            lines.push({ item, requested_qty: qty });
            itemPicker.value = '';
            qtyInput.value = '';
            _renderLines();
        },
    });

    function _renderLines() {
        clear(linesHost);
        if (lines.length === 0) {
            linesHost.appendChild(el('p', { class: 'sup-muted', text: 'Sin líneas todavía.' }));
            return;
        }
        const thead = el('thead', {}, [el('tr', {}, [
            el('th', { text: 'Ítem' }), el('th', { text: 'Cantidad' }), el('th', {}),
        ])]);
        const tbody = el('tbody', {}, lines.map((line, idx) =>
            el('tr', {}, [
                el('td', { text: `${line.item.code} — ${line.item.name}` }),
                el('td', { text: formatNumber(line.requested_qty) }),
                el('td', { class: 'sup-row-actions' }, [
                    el('button', {
                        class: 'sup-icon-btn', type: 'button', title: 'Eliminar',
                        html: '<i class="fa-solid fa-xmark"></i>',
                        onClick: () => { lines.splice(idx, 1); _renderLines(); },
                    }),
                ]),
            ]),
        ));
        linesHost.appendChild(el('div', { class: 'sup-table-wrap' }, [
            el('table', { class: 'sup-table' }, [thead, tbody]),
        ]));
    }

    _renderLines();

    const notesIn = el('textarea', { name: 'notes', placeholder: 'Notas opcionales' });

    const body = el('div', { class: 'sup-stack' }, [
        el('div', { class: 'sup-field-row' }, [
            el('label', { class: 'sup-field' }, [
                el('span', { text: 'Ítem disponible' }), itemPicker,
            ]),
            el('label', { class: 'sup-field' }, [
                el('span', { text: 'Cantidad' }), qtyInput,
            ]),
        ]),
        el('div', {}, [addBtn]),
        el('div', { class: 'sup-mt-md' }, [linesHost]),
        el('label', { class: 'sup-field sup-mt-md' }, [
            el('span', { text: 'Notas' }), notesIn,
        ]),
        errEl,
    ]);

    const submitBtn = el('button', {
        class: 'sup-btn sup-btn-primary', text: 'Crear solicitud',
        onClick: async () => {
            errEl.hidden = true;
            if (lines.length === 0) {
                errEl.textContent = 'Agrega al menos una línea.';
                errEl.hidden = false;
                return;
            }
            try {
                await api.createRequest({
                    notes: notesIn.value || null,
                    details: lines.map(l => ({
                        item_id: Number(l.item.id),
                        requested_qty: Number(l.requested_qty),
                    })),
                });
                showToast('Solicitud creada', 'success');
                closeModal();
                onSuccess();
            } catch (err) {
                errEl.textContent = err.message;
                errEl.hidden = false;
            }
        },
    });

    openModal({
        title: 'Nueva solicitud',
        body,
        footer: [
            el('button', { class: 'sup-btn sup-btn-ghost', text: 'Cancelar', onClick: closeModal }),
            submitBtn,
        ],
        wide: true,
    });
}

