/**
 * Reusable supply-request detail modal.
 *
 * Used by both the RequestsPage (admin/warehouse listing) and the
 * REQUESTER-flavored DashboardPage so the detail UI stays consistent
 * regardless of where the user opens it from.
 *
 * Exposes a single entry point:
 *
 *     openRequestDetailModal({ api, requestId, onChange })
 *
 * where `onChange` is called after every successful state transition so
 * the caller can refresh whatever list/aggregation it is rendering.
 */
import { getEmail, hasRole, ROLES } from '../auth.js';
import {
    closeModal,
    el,
    formatDate,
    formatNumber,
    openModal,
    showToast,
    statusBadge,
} from '../ui.js';


export async function openRequestDetailModal({ api, requestId, onChange }) {
    const ctx = { api, onChange: onChange || (() => {}) };
    openModal({ title: 'Cargando solicitud…', body: 'Cargando…' });
    try {
        const detail = await ctx.api.getRequest(requestId);
        _renderDetail(ctx, detail);
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


function _renderDetail(ctx, detail) {
    const meta = el('div', { class: 'sup-stack' }, [
        el('div', { class: 'sup-flex-between' }, [
            el('span', {}, [statusBadge(detail.status)]),
            el('span', { class: 'sup-muted', text: detail.code }),
        ]),
        el('p', { class: 'sup-muted', text: `Solicitante: ${detail.requester_email}` }),
        detail.notes ? el('p', { text: `Notas: ${detail.notes}` }) : null,
    ].filter(Boolean));

    const linesTable = el('div', { class: 'sup-table-wrap' }, [
        el('table', { class: 'sup-table' }, [
            el('thead', {}, [el('tr', {}, [
                el('th', { text: 'Ítem' }),
                el('th', { text: 'Solicitado' }),
                el('th', { text: 'Entregado' }),
            ])]),
            el('tbody', {}, detail.details.map(d =>
                el('tr', {}, [
                    el('td', { text: `#${d.item_id}` }),
                    el('td', { text: formatNumber(d.requested_qty) }),
                    el('td', { text: formatNumber(d.delivered_qty) }),
                ]),
            )),
        ]),
    ]);

    const historyTable = el('div', { class: 'sup-table-wrap' }, [
        el('table', { class: 'sup-table' }, [
            el('thead', {}, [el('tr', {}, [
                el('th', { text: 'De' }), el('th', { text: 'A' }),
                el('th', { text: 'Por' }), el('th', { text: 'Fecha' }), el('th', { text: 'Motivo' }),
            ])]),
            el('tbody', {}, detail.status_history.map(h =>
                el('tr', {}, [
                    el('td', {}, [h.from_status ? statusBadge(h.from_status) : el('span', { text: '—' })]),
                    el('td', {}, [statusBadge(h.to_status)]),
                    el('td', { text: h.changed_by }),
                    el('td', { text: formatDate(h.changed_at, true) }),
                    el('td', { text: h.reason || '—' }),
                ]),
            )),
        ]),
    ]);

    const body = el('div', { class: 'sup-stack' }, [
        meta,
        el('h4', { text: 'Líneas' }),
        linesTable,
        el('h4', { text: 'Historial de estados' }),
        historyTable,
    ]);

    openModal({
        title: `Solicitud ${detail.code}`,
        body,
        footer: _buildTransitionButtons(ctx, detail),
        wide: true,
    });
}


function _buildTransitionButtons(ctx, request) {
    const buttons = [];
    const isOwner = request.requester_email === getEmail();
    const isWarehouse = hasRole(ROLES.WAREHOUSE_MANAGER, ROLES.ADMIN);
    const isAdmin = hasRole(ROLES.ADMIN);

    if (request.status === 'CREATED' && (isOwner || isAdmin)) {
        buttons.push(_actionBtn('Eliminar', 'sup-btn-danger', 'fa-trash',
            () => _confirmAndRun(ctx,
                `Eliminar solicitud ${request.code}?`,
                () => ctx.api.deleteRequest(request.id),
                'Solicitud eliminada',
                { closeAfter: true })));
    }

    if (request.status === 'CREATED' && isWarehouse) {
        buttons.push(_actionBtn('Procesar', 'sup-btn-primary', 'fa-play',
            () => _runAndReopen(ctx, request.id,
                () => ctx.api.processRequest(request.id),
                'Solicitud en proceso')));
    }

    if (request.status === 'IN_PROCESS' && isWarehouse) {
        buttons.push(_actionBtn('Entregar', 'sup-btn-success', 'fa-truck',
            () => _openDeliverDialog(ctx, request)));
        buttons.push(_actionBtn('Rechazar', 'sup-btn-danger', 'fa-ban',
            () => _openReasonDialog('Motivo del rechazo', reason =>
                _runAndReopen(ctx, request.id,
                    () => ctx.api.rejectRequest(request.id, reason),
                    'Solicitud rechazada'))));
        buttons.push(_actionBtn('Anular', 'sup-btn-ghost', 'fa-xmark',
            () => _openReasonDialog('Motivo de la anulación', reason =>
                _runAndReopen(ctx, request.id,
                    () => ctx.api.cancelRequest(request.id, reason),
                    'Solicitud anulada'))));
    }

    if (request.status === 'DELIVERED' && (isOwner || isAdmin)) {
        buttons.push(_actionBtn('Confirmar recepción', 'sup-btn-success', 'fa-check',
            () => _runAndReopen(ctx, request.id,
                () => ctx.api.closeRequest(request.id),
                'Solicitud cerrada')));
    }

    buttons.push(el('button', {
        class: 'sup-btn sup-btn-ghost', text: 'Cerrar', onClick: closeModal,
    }));
    return buttons;
}


function _actionBtn(label, klass, icon, onClick) {
    return el('button', {
        class: `sup-btn ${klass}`,
        html: `<i class="fa-solid ${icon}"></i> ${label}`,
        onClick,
    });
}


async function _confirmAndRun(ctx, message, fn, successMsg, { closeAfter = false } = {}) {
    if (!confirm(message)) return;
    try {
        await fn();
        showToast(successMsg, 'success');
        ctx.onChange();
        if (closeAfter) closeModal();
    } catch (err) {
        showToast(err.message, 'error');
    }
}


async function _runAndReopen(ctx, requestId, fn, successMsg) {
    try {
        await fn();
        showToast(successMsg, 'success');
        await openRequestDetailModal({
            api: ctx.api, requestId, onChange: ctx.onChange,
        });
        ctx.onChange();
    } catch (err) {
        showToast(err.message, 'error');
    }
}


function _openReasonDialog(title, onConfirm) {
    const textarea = el('textarea', {
        name: 'reason',
        placeholder: 'Detalle el motivo (obligatorio para rechazo).',
        required: true,
    });
    const errEl = el('p', { class: 'sup-form-error', hidden: true });

    const body = el('div', { class: 'sup-stack' }, [
        el('label', { class: 'sup-field' }, [
            el('span', { text: 'Motivo' }), textarea,
        ]),
        errEl,
    ]);

    const submit = el('button', {
        class: 'sup-btn sup-btn-primary', text: 'Confirmar',
        onClick: async () => {
            const value = textarea.value.trim();
            if (!value) {
                errEl.textContent = 'El motivo es obligatorio.';
                errEl.hidden = false;
                return;
            }
            try {
                await onConfirm(value);
            } catch (err) {
                errEl.textContent = err.message;
                errEl.hidden = false;
            }
        },
    });

    openModal({
        title,
        body,
        footer: [
            el('button', { class: 'sup-btn sup-btn-ghost', text: 'Cancelar', onClick: closeModal }),
            submit,
        ],
    });
}


async function _openDeliverDialog(ctx, request) {
    const deliveries = request.details.map(d => ({
        item_id: d.item_id,
        requested_qty: Number(d.requested_qty),
        delivered_qty: Number(d.requested_qty),
    }));

    const tbody = el('tbody', {}, deliveries.map((line, idx) => {
        const input = el('input', {
            type: 'number', step: '0.01', min: '0.01', max: line.requested_qty,
            value: line.delivered_qty,
        });
        input.onchange = () => { deliveries[idx].delivered_qty = Number(input.value); };
        return el('tr', {}, [
            el('td', { text: `#${line.item_id}` }),
            el('td', { text: formatNumber(line.requested_qty) }),
            el('td', {}, [input]),
        ]);
    }));

    const table = el('div', { class: 'sup-table-wrap' }, [
        el('table', { class: 'sup-table' }, [
            el('thead', {}, [el('tr', {}, [
                el('th', { text: 'Ítem' }),
                el('th', { text: 'Solicitado' }),
                el('th', { text: 'Entregar' }),
            ])]),
            tbody,
        ]),
    ]);
    const notesIn = el('textarea', { name: 'notes', placeholder: 'Observaciones (opcional)' });
    const errEl = el('p', { class: 'sup-form-error', hidden: true });

    const body = el('div', { class: 'sup-stack' }, [
        el('p', {
            class: 'sup-muted',
            text: 'Cantidades modificables; los valores se descontarán del kárdex.',
        }),
        table,
        el('label', { class: 'sup-field' }, [
            el('span', { text: 'Notas' }), notesIn,
        ]),
        errEl,
    ]);

    const submit = el('button', {
        class: 'sup-btn sup-btn-success',
        html: '<i class="fa-solid fa-truck"></i> Confirmar entrega',
        onClick: async () => {
            try {
                await ctx.api.deliverRequest(request.id, {
                    notes: notesIn.value || null,
                    details: deliveries.map(d => ({
                        item_id: d.item_id, delivered_qty: d.delivered_qty,
                    })),
                });
                showToast('Solicitud entregada', 'success');
                await openRequestDetailModal({
                    api: ctx.api, requestId: request.id, onChange: ctx.onChange,
                });
                ctx.onChange();
            } catch (err) {
                errEl.textContent = err.message;
                errEl.hidden = false;
            }
        },
    });

    openModal({
        title: `Entregar ${request.code}`,
        body,
        footer: [
            el('button', { class: 'sup-btn sup-btn-ghost', text: 'Cancelar', onClick: closeModal }),
            submit,
        ],
        wide: true,
    });
}
