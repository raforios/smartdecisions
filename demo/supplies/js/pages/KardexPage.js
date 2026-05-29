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
    el,
    formatDate,
    formatNumber,
    openModal,
    showToast,
} from '../ui.js';

export async function mountKardex({ host, actions, api }) {
    clear(host);
    actions.innerHTML = '';

    actions.appendChild(el('button', {
        class: 'sup-btn sup-btn-primary',
        html: '<i class="fa-solid fa-pen-to-square"></i> Ajuste manual',
        onClick: () => _openAdjustmentModal(api, () => state.itemId && _loadKardex(state)),
    }));

    const state = { api, host, itemId: null, items: [], dateFrom: '', dateTo: '' };

    try {
        state.items = await api.listItems({ limit: 500 });
    } catch (err) {
        host.appendChild(el('p', { class: 'sup-form-error', text: err.message }));
        return;
    }

    const itemSel = el('select', { name: 'item_id' });
    itemSel.appendChild(el('option', { value: '', text: '— Selecciona un ítem —' }));
    state.items.forEach(it => {
        itemSel.appendChild(el('option', {
            value: it.id,
            text: `${it.code} — ${it.name} (stock ${formatNumber(it.current_stock)})`,
        }));
    });
    itemSel.onchange = () => { state.itemId = itemSel.value || null; _loadKardex(state); };

    const fromIn = el('input', { type: 'date' });
    fromIn.onchange = () => { state.dateFrom = fromIn.value; _loadKardex(state); };
    const toIn = el('input', { type: 'date' });
    toIn.onchange = () => { state.dateTo = toIn.value; _loadKardex(state); };

    const filters = el('div', { class: 'sup-filters' }, [
        el('label', { class: 'sup-field' }, [el('span', { text: 'Ítem' }), itemSel]),
        el('label', { class: 'sup-field' }, [el('span', { text: 'Desde' }), fromIn]),
        el('label', { class: 'sup-field' }, [el('span', { text: 'Hasta' }), toIn]),
    ]);
    host.appendChild(filters);

    state.ledgerHost = el('div', {});
    host.appendChild(state.ledgerHost);
    state.ledgerHost.appendChild(el('p', { class: 'sup-placeholder', text: 'Selecciona un ítem para ver su kárdex.' }));
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
            el('th', { text: 'Balance antes' }),
            el('th', { text: 'Balance después' }),
            el('th', { text: 'Lote' }),
            el('th', { text: 'Usuario' }),
            el('th', { text: 'Notas' }),
        ])]);
        const tbody = el('tbody', {}, rows.map(m => el('tr', {}, [
            el('td', { text: formatDate(m.created_at, true) }),
            el('td', {}, [_movementBadge(m.movement_type)]),
            el('td', { text: `${m.reference_type}${m.reference_id ? '#' + m.reference_id : ''}` }),
            el('td', { text: formatNumber(m.quantity) }),
            el('td', { text: formatNumber(m.balance_before) }),
            el('td', { text: formatNumber(m.balance_after) }),
            el('td', { text: m.batch_code || '—' }),
            el('td', { text: m.created_by }),
            el('td', { text: m.notes || '—' }),
        ])));
        state.ledgerHost.appendChild(el('div', { class: 'sup-table-wrap' }, [
            el('table', { class: 'sup-table' }, [thead, tbody]),
        ]));
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
        const itemSel = el('select', { name: 'item_id', required: true });
        itemSel.appendChild(el('option', { value: '', text: '— Elegir ítem —' }));
        items.forEach(it => {
            itemSel.appendChild(el('option', {
                value: it.id, text: `${it.code} — ${it.name}`,
            }));
        });

        const form = el('form', { class: 'sup-stack' }, [
            el('label', { class: 'sup-field' }, [el('span', { text: 'Ítem' }), itemSel]),
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
                    await api.createKardexAdjustment({
                        item_id: Number(fd.get('item_id')),
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
