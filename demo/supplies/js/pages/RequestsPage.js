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
    collapsible,
    el,
    formatDate,
    formatNumber,
    itemPicker,
    openModal,
    showToast,
    statusBadge,
} from '../ui.js';
import { openRequestDetailModal } from './RequestDetailModal.js';

// The requester types the same name, position and unit on every request; the
// browser remembers them so only the articles change from one form to the next.
const IDENTITY_KEY = 'supplies_requester_identity';

function _rememberedIdentity() {
    try {
        return JSON.parse(localStorage.getItem(IDENTITY_KEY)) || {};
    } catch (err) {
        return {};
    }
}

function _rememberIdentity(identity) {
    localStorage.setItem(IDENTITY_KEY, JSON.stringify(identity));
}

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
    const box = collapsible({
        title: 'Solicitudes',
        subtitle: `${rows.length} registro(s)`,
        stateKey: 'requests.list',
    });
    box.body.appendChild(el('div', { class: 'sup-table-wrap' }, [
        el('table', { class: 'sup-table' }, [thead, tbody]),
    ]));
    return box.section;
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

    /**
     * Shows a validation message. The error line sits at the bottom of a
     * scrollable modal, so it is scrolled into view — otherwise pressing
     * "Agregar línea" with a bad quantity looks like nothing happened.
     */
    function _fail(message) {
        errEl.textContent = message;
        errEl.hidden = false;
        errEl.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }

    // Type-to-filter instead of a 380-option select: the requester knows the
    // article by name or code, not by its position in a dropdown.
    const picker = itemPicker({
        items: availableItems,
        placeholder: 'Buscar artículo por código o descripción…',
        onSelect: item => _showAvailability(item),
    });

    const qtyInput = el('input', { type: 'number', step: '0.01', min: '0.01', name: 'qty' });
    const availabilityEl = el('p', { class: 'sup-muted sup-availability', text: '' });

    /**
     * States the ceiling explicitly when an article is picked: the requester
     * should not have to submit the form to learn how many units are left.
     * Declared as a function so the picker callback can reach it before the
     * consts above it are initialized.
     */
    function _showAvailability(item) {
        if (!item) {
            availabilityEl.textContent = '';
            qtyInput.removeAttribute('max');
            return;
        }
        const left = _remainingFor(item);
        qtyInput.max = String(left);
        availabilityEl.textContent =
            `Disponible para solicitar: ${formatNumber(left)}`
            + (_takenFor(item) ? ` (ya pediste ${formatNumber(_takenFor(item))} aquí)` : '');
    }

    function _takenFor(item) {
        return lines
            .filter(line => line.item.id === item.id)
            .reduce((acc, line) => acc + Number(line.requested_qty), 0);
    }

    function _remainingFor(item) {
        const left = Number(item.available_stock ?? 0) - _takenFor(item);
        return left > 0 ? left : 0;
    }

    const addBtn = el('button', {
        class: 'sup-btn sup-btn-ghost',
        type: 'button',
        text: 'Agregar línea',
        onClick: () => {
            const item = picker.selected();
            const qty = Number(qtyInput.value);
            if (!item || !qty || qty <= 0) {
                _fail('Selecciona ítem y cantidad mayor a cero.');
                return;
            }
            // Catch it here rather than letting the backend reject the whole
            // request after the user filled every line.
            if (qty > _remainingFor(item)) {
                _fail(`Solo hay ${formatNumber(_remainingFor(item))} unidad(es) disponibles `
                      + `de ${item.code}. Ajusta la cantidad.`);
                return;
            }
            errEl.hidden = true;
            lines.push({ item, requested_qty: qty });
            picker.reset();
            qtyInput.value = '';
            availabilityEl.textContent = '';
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

    const notesIn = el('textarea', {
        name: 'notes', placeholder: 'Justificación de la solicitud',
    });

    // These three are printed on the FORMULARIO - SOLICITUD DE ALMACENES and
    // signed on paper, so they are captured with the request.
    const nameIn = el('input', { name: 'requester_name', required: true });
    const positionIn = el('input', { name: 'requester_position', required: true });
    const unitIn = el('input', { name: 'requester_unit', required: true });
    const remembered = _rememberedIdentity();
    nameIn.value = remembered.requester_name || '';
    positionIn.value = remembered.requester_position || '';
    unitIn.value = remembered.requester_unit || '';

    const body = el('div', { class: 'sup-stack' }, [
        el('div', { class: 'sup-field-row' }, [
            el('label', { class: 'sup-field' }, [
                el('span', { text: 'Solicitado por (nombre completo)' }), nameIn,
            ]),
            el('label', { class: 'sup-field' }, [
                el('span', { text: 'Cargo' }), positionIn,
            ]),
        ]),
        el('label', { class: 'sup-field' }, [
            el('span', { text: 'Dirección / Unidad' }), unitIn,
        ]),
        el('div', { class: 'sup-field-row' }, [
            el('label', { class: 'sup-field' }, [
                el('span', { text: 'Ítem disponible' }), picker.el,
            ]),
            el('label', { class: 'sup-field' }, [
                el('span', { text: 'Cantidad' }), qtyInput,
            ]),
        ]),
        availabilityEl,
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
                _fail('Agrega al menos una línea.');
                return;
            }
            const identity = {
                requester_name: nameIn.value.trim(),
                requester_position: positionIn.value.trim(),
                requester_unit: unitIn.value.trim(),
            };
            if (!identity.requester_name || !identity.requester_position
                || !identity.requester_unit) {
                _fail('Completa nombre, cargo y dirección/unidad: '
                      + 'se imprimen en el formulario de solicitud.');
                return;
            }
            try {
                await api.createRequest({
                    ...identity,
                    notes: notesIn.value || null,
                    details: lines.map(l => ({
                        item_id: Number(l.item.id),
                        requested_qty: Number(l.requested_qty),
                    })),
                });
                _rememberIdentity(identity);
                showToast('Solicitud creada', 'success');
                closeModal();
                onSuccess();
            } catch (err) {
                _fail(err.message);
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

