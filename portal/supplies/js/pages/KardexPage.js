/**
 * Kardex page.
 *
 * Pick an item (or type its id), see its ledger and post manual
 * adjustments. The ledger is append-only on the backend: every correction
 * generates a new ADJUSTMENT row with the signed delta.
 */
import {
    clear,
    closeModal,
    collapsible,
    el,
    formatDate,
    formatMoney,
    formatNumber,
    itemPicker,
    openModal,
    showToast,
} from '../ui.js';

export async function mountKardex({ host, actions, api, router, params = [] }) {
    clear(host);
    actions.innerHTML = '';

    actions.appendChild(el('button', {
        class: 'sup-btn sup-btn-primary',
        html: '<i class="fa-solid fa-pen-to-square"></i> Ajuste manual',
        onClick: () => _openAdjustmentModal(api, () => state.itemId && _loadKardex(state)),
    }));

    // `#/kardex/<id>` arrives from the catalog's "Ver movimiento del artículo",
    // so the page opens already focused on that item.
    const preselectedId = params[0] ? String(Number(params[0])) : null;
    const state = { api, host, itemId: preselectedId, items: [], dateFrom: '', dateTo: '' };

    try {
        state.items = await api.listItems({ limit: 500 });
    } catch (err) {
        host.appendChild(el('p', { class: 'sup-form-error', text: err.message }));
        return;
    }

    // Arriving from the catalog: offer the way back, otherwise the only exit
    // is the main menu, which loses the list the user was looking at.
    if (preselectedId && router) {
        host.appendChild(el('button', {
            class: 'sup-back-link',
            html: '<i class="fa-solid fa-arrow-left"></i> Volver al catálogo',
            onClick: () => router.go('catalog'),
        }));
    }

    const picker = itemPicker({
        items: state.items,
        placeholder: 'Buscar por código o descripción…',
        onSelect: item => {
            state.itemId = item ? item.id : null;
            _renderItemHeader(state);
            if (item) _loadKardex(state);
        },
    });
    const preselected = state.items.find(it => String(it.id) === String(preselectedId));
    if (preselected) picker.el.querySelector('input').value =
        `${preselected.code} — ${preselected.name}`;

    const fromIn = el('input', { type: 'date' });
    fromIn.onchange = () => { state.dateFrom = fromIn.value; _loadKardex(state); };
    const toIn = el('input', { type: 'date' });
    toIn.onchange = () => { state.dateTo = toIn.value; _loadKardex(state); };

    const filters = el('div', { class: 'sup-filters' }, [
        el('label', { class: 'sup-field' }, [el('span', { text: 'Ítem' }), picker.el]),
        el('label', { class: 'sup-field' }, [el('span', { text: 'Desde' }), fromIn]),
        el('label', { class: 'sup-field' }, [el('span', { text: 'Hasta' }), toIn]),
    ]);
    host.appendChild(filters);

    state.headerHost = el('div', {});
    host.appendChild(state.headerHost);
    state.ledgerHost = el('div', {});
    host.appendChild(state.ledgerHost);

    if (state.itemId) {
        _renderItemHeader(state);
        await _loadKardex(state);
    } else {
        state.ledgerHost.appendChild(el('p', {
            class: 'sup-placeholder', text: 'Selecciona un ítem para ver su kárdex.',
        }));
    }
}

/**
 * Identity card of the selected item above its ledger, so a kardex opened
 * from the catalog is self-explanatory instead of a bare table of numbers.
 */
function _renderItemHeader(state) {
    clear(state.headerHost);
    const item = state.items.find(it => String(it.id) === String(state.itemId));
    if (!item) return;
    state.headerHost.appendChild(el('div', { class: 'sup-card sup-card-padded sup-kardex-head' }, [
        el('h3', { text: `${item.code} — ${item.name}` }),
        el('p', { class: 'sup-muted', text: `Stock actual: ${formatNumber(item.current_stock)}` }),
    ]));
}

async function _loadKardex(state) {
    if (!state.itemId) return;
    clear(state.ledgerHost);
    state.ledgerHost.appendChild(el('p', { class: 'sup-placeholder', text: 'Cargando movimientos…' }));
    try {
        const params = {};
        if (state.dateFrom) params.date_from = `${state.dateFrom}T00:00:00`;
        if (state.dateTo) params.date_to = `${state.dateTo}T23:59:59`;
        const rows = await state.api.listKardexForItem(state.itemId, params);
        clear(state.ledgerHost);
        if (rows.length === 0) {
            state.ledgerHost.appendChild(el('div', { class: 'sup-empty', text: 'Sin movimientos en el rango.' }));
            return;
        }
        const thead = el('thead', {}, [el('tr', {}, [
            el('th', { text: 'Fecha' }),
            el('th', { text: 'Tipo' }),
            el('th', { text: 'Origen' }),
            el('th', { text: 'Cantidad' }),
            el('th', { text: 'Costo unitario' }),
            el('th', { text: 'Costo total' }),
            el('th', { text: 'N° ingreso' }),
            el('th', { text: 'Balance antes' }),
            el('th', { text: 'Balance después' }),
            el('th', { text: 'Usuario' }),
            el('th', { text: 'Notas' }),
        ])]);
        const tbody = el('tbody', {}, rows.map(m => el('tr', {}, [
            el('td', { text: formatDate(m.created_at, true) }),
            el('td', {}, [_movementBadge(m.movement_type)]),
            el('td', { text: `${m.reference_type}${m.reference_id ? '#' + m.reference_id : ''}` }),
            el('td', { text: formatNumber(m.quantity) }),
            el('td', { text: m.unit_cost != null ? formatMoney(m.unit_cost) : '—' }),
            el('td', { text: m.total_cost != null ? formatMoney(m.total_cost) : '—' }),
            el('td', { text: m.source_entry_id ? `#${m.source_entry_id}` : '—' }),
            el('td', { text: formatNumber(m.balance_before) }),
            el('td', { text: formatNumber(m.balance_after) }),
            el('td', { text: m.created_by }),
            el('td', { text: m.notes || '—' }),
        ])));
        const box = collapsible({
            title: 'Movimientos del ítem',
            subtitle: `${rows.length} movimiento(s)`,
            open: true,
            stateKey: 'kardex.ledger',
        });
        box.body.appendChild(el('div', { class: 'sup-table-wrap' }, [
            el('table', { class: 'sup-table' }, [thead, tbody]),
        ]));
        state.ledgerHost.appendChild(box.section);
    } catch (err) {
        clear(state.ledgerHost);
        state.ledgerHost.appendChild(el('p', { class: 'sup-form-error', text: err.message }));
    }
}

function _movementBadge(type) {
    const map = {
        IN: { class: 'sup-badge-delivered', label: 'Entrada' },
        OUT: { class: 'sup-badge-rejected', label: 'Salida' },
        ADJUSTMENT: { class: 'sup-badge-cancelled', label: 'Ajuste' },
    };
    const cfg = map[type] || { class: 'sup-badge-closed', label: type };
    return el('span', { class: `sup-badge ${cfg.class}`, text: cfg.label });
}

function _openAdjustmentModal(api, onSuccess) {
    api.listItems({ limit: 500 }).then(items => {
        const picker = itemPicker({ items, placeholder: 'Buscar el ítem a ajustar…' });

        const form = el('form', { class: 'sup-stack' }, [
            el('label', { class: 'sup-field' }, [el('span', { text: 'Ítem' }), picker.el]),
            el('label', { class: 'sup-field' }, [
                el('span', { text: 'Cantidad (positiva añade, negativa resta)' }),
                el('input', { type: 'number', step: '0.01', name: 'quantity', required: true }),
            ]),
            el('label', { class: 'sup-field' }, [
                el('span', { text: 'Motivo' }),
                el('textarea', { name: 'notes', placeholder: 'Ej: inventario físico, merma, etc.' }),
            ]),
        ]);
        const errEl = el('p', { class: 'sup-form-error', hidden: true });
        form.appendChild(errEl);

        const submit = el('button', {
            class: 'sup-btn sup-btn-primary', text: 'Registrar ajuste',
            onClick: async () => {
                errEl.hidden = true;
                const fd = new FormData(form);
                try {
                    if (!picker.value()) {
                        errEl.textContent = 'Elige un ítem.';
                        errEl.hidden = false;
                        return;
                    }
                    await api.createKardexAdjustment({
                        item_id: picker.value(),
                        quantity: Number(fd.get('quantity')),
                        notes: fd.get('notes') || null,
                    });
                    showToast('Ajuste registrado', 'success');
                    closeModal();
                    onSuccess?.();
                } catch (err) {
                    errEl.textContent = err.message;
                    errEl.hidden = false;
                }
            },
        });

        openModal({
            title: 'Ajuste manual de kárdex',
            body: form,
            footer: [
                el('button', { class: 'sup-btn sup-btn-ghost', text: 'Cancelar', onClick: closeModal }),
                submit,
            ],
        });
    }).catch(err => showToast(err.message, 'error'));
}
