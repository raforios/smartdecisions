/**
 * Dashboard page.
 *
 * Branches by role:
 *   - ADMIN / WAREHOUSE_MANAGER -> global KPIs from /dashboard/summary and
 *     /dashboard/recent-activity.
 *   - REQUESTER -> own-data dashboard built from /v1/supplies/requests
 *     (the backend auto-filters to the caller's email). Shows aggregated
 *     KPIs and the list of own requests with click-to-detail.
 */
import { getEmail, hasRole, ROLES } from '../auth.js';
import {
    clear,
    collapsible,
    el,
    formatDate,
    formatNumber,
    showToast,
    statusBadge,
} from '../ui.js';
import { openRequestDetailModal } from './RequestDetailModal.js';

const ENTRY_TYPE_LABEL = {
    COMPRA: 'Compra',
    DONACION_TRANSFERENCIA: 'Donación y/o Transferencia',
    REINGRESO: 'Reingreso',
};

export async function mountDashboard({ host, actions, api, router }) {
    clear(host);
    actions.innerHTML = '';

    if (hasRole(ROLES.ADMIN, ROLES.WAREHOUSE_MANAGER)) {
        return _mountAdminDashboard({ host, api });
    }
    return _mountRequesterDashboard({ host, actions, api, router });
}


async function _mountAdminDashboard({ host, api }) {
    host.appendChild(_skeleton());

    try {
        const [summary, activity] = await Promise.all([
            api.dashboardSummary(),
            api.dashboardRecentActivity(8),
        ]);
        clear(host);
        host.appendChild(_renderKpis(summary));
        host.appendChild(_renderActivity(activity));
    } catch (err) {
        clear(host);
        host.appendChild(el('div', { class: 'sup-card sup-card-padded' }, [
            el('p', { class: 'sup-form-error', text: `Error cargando dashboard: ${err.message}` }),
        ]));
        showToast(`Dashboard: ${err.message}`, 'error');
    }
}


function _skeleton() {
    return el('div', { class: 'sup-stack' }, [
        el('div', { class: 'sup-kpi-grid' }, _placeholderKpis(8)),
        el('div', { class: 'sup-card sup-card-padded sup-placeholder', text: 'Cargando…' }),
    ]);
}

function _placeholderKpis(count) {
    return Array.from({ length: count }, () =>
        el('div', { class: 'sup-kpi' }, [
            el('p', { class: 'sup-kpi-label', text: '—' }),
            el('p', { class: 'sup-kpi-value', text: '…' }),
        ]),
    );
}

function _renderKpis(summary) {
    const grid = el('div', { class: 'sup-kpi-grid' });
    const items = [
        { label: 'Items activos', value: summary.active_items, help: `${summary.total_items} totales` },
        { label: 'Bajo mínimo', value: summary.items_below_min,
          help: 'requieren reposición', variant: summary.items_below_min > 0 ? 'is-warning' : '' },
        { label: 'Solicitudes abiertas', value: summary.open_requests,
          help: 'creadas + en proceso + entregadas' },
        { label: 'En proceso', value: summary.requests_in_process,
          help: 'almacén procesando' },
        { label: 'Pendientes de cierre', value: summary.requests_delivered_pending_close,
          help: 'esperan conformidad', variant: summary.requests_delivered_pending_close > 0
              ? 'is-success' : '' },
        { label: 'Notas de ingreso', value: summary.total_entries,
          help: 'registradas en total' },
        { label: 'Ingresos (30 días)', value: summary.entries_last_30_days,
          help: 'notas del último mes' },
    ];
    items.forEach(kpi => grid.appendChild(_kpiCard(kpi)));
    return grid;
}

function _kpiCard({ label, value, help, variant }) {
    return el('div', { class: `sup-kpi ${variant || ''}`.trim() }, [
        el('p', { class: 'sup-kpi-label', text: label }),
        el('p', { class: 'sup-kpi-value', text: formatNumber(value, 0) }),
        help ? el('p', { class: 'sup-kpi-help', text: help }) : null,
    ]);
}

function _renderActivity(activity) {
    const wrap = el('div', { class: 'sup-stack' });

    wrap.appendChild(_section('Solicitudes recientes',
        _table(
            ['Código', 'Solicitante', 'Items', 'Estado', 'Solicitado', 'Cerrado'],
            activity.recent_requests,
            r => [
                r.code,
                r.requester_email,
                formatNumber(r.total_items, 0),
                statusBadge(r.status),
                formatDate(r.requested_at, true),
                r.closed_at ? formatDate(r.closed_at, true) : '—',
            ],
        ),
        activity.recent_requests.length,
    ));

    wrap.appendChild(_section('Notas de ingreso recientes',
        _table(
            ['Código', 'Tipo', 'Proveedor', 'Líneas', 'Total', 'Creado'],
            activity.recent_entries,
            r => [
                r.code,
                ENTRY_TYPE_LABEL[r.entry_type] || r.entry_type,
                r.supplier || '—',
                formatNumber(r.total_lines, 0),
                formatNumber(r.total),
                formatDate(r.created_at, true),
            ],
        ),
        activity.recent_entries.length,
    ));

    wrap.appendChild(_section('Movimientos de kárdex',
        _table(
            ['Item', 'Tipo', 'Origen', 'Cantidad', 'Balance', 'Fecha'],
            activity.recent_movements,
            m => [
                `#${m.item_id}`,
                m.movement_type,
                `${m.reference_type}${m.reference_id ? '#' + m.reference_id : ''}`,
                formatNumber(m.quantity),
                `${formatNumber(m.balance_before)} → ${formatNumber(m.balance_after)}`,
                formatDate(m.created_at, true),
            ],
        ),
        activity.recent_movements.length,
    ));

    return wrap;
}

function _section(title, content, count = null) {
    // Collapsed by default: the dashboard is meant to be read at a glance, and
    // three stacked tables push the KPIs off screen.
    const box = collapsible({
        title,
        subtitle: count === null ? '' : `${count} registro(s)`,
        stateKey: `dashboard.${title}`,
    });
    box.body.appendChild(content);
    return box.section;
}

function _table(headers, rows, mapper) {
    if (!rows || rows.length === 0) {
        return el('div', { class: 'sup-empty', text: 'Sin registros.' });
    }
    const thead = el('thead', {}, [
        el('tr', {}, headers.map(h => el('th', { text: h }))),
    ]);
    const tbody = el('tbody', {}, rows.map(r =>
        el('tr', {}, mapper(r).map(cell =>
            el('td', cell instanceof Node ? {} : { text: cell ?? '—' }, cell instanceof Node ? cell : []),
        )),
    ));
    return el('div', { class: 'sup-table-wrap' }, [el('table', { class: 'sup-table' }, [thead, tbody])]);
}


// --------------------------------------------------------------------- //
// REQUESTER dashboard                                                    //
// --------------------------------------------------------------------- //
async function _mountRequesterDashboard({ host, actions, api, router }) {
    actions.appendChild(el('button', {
        class: 'sup-btn sup-btn-primary',
        html: '<i class="fa-solid fa-plus"></i> Nueva solicitud',
        onClick: () => router.go('requests'),
    }));

    host.appendChild(el('p', { class: 'sup-placeholder', text: 'Cargando tus solicitudes…' }));

    try {
        const rows = await api.listRequests({});
        clear(host);
        host.appendChild(_renderRequesterKpis(rows));
        host.appendChild(_renderMyRequestsTable(rows, api));
    } catch (err) {
        clear(host);
        host.appendChild(el('div', { class: 'sup-card sup-card-padded' }, [
            el('p', { class: 'sup-form-error', text: `Error cargando tus solicitudes: ${err.message}` }),
        ]));
        showToast(`Dashboard: ${err.message}`, 'error');
    }
}


function _renderRequesterKpis(rows) {
    const counts = {
        total: rows.length,
        open: rows.filter(r => r.status === 'CREATED' || r.status === 'IN_PROCESS').length,
        waitingConfirmation: rows.filter(r => r.status === 'DELIVERED').length,
        closed: rows.filter(r => r.status === 'CLOSED').length,
        rejectedOrCancelled: rows.filter(r =>
            r.status === 'REJECTED' || r.status === 'CANCELLED').length,
    };

    const greeting = el('div', { class: 'sup-card sup-card-padded sup-mb-md' }, [
        el('p', { class: 'sup-muted',
                  text: `Hola, ${getEmail() || 'usuario'}.` }),
        el('h3', { text: 'Estas son tus solicitudes y el estado de cada una.' }),
    ]);

    const grid = el('div', { class: 'sup-kpi-grid' }, [
        _kpiCard({ label: 'Total mías', value: counts.total }),
        _kpiCard({
            label: 'En curso', value: counts.open,
            help: 'creadas o en proceso',
            variant: counts.open > 0 ? 'is-warning' : '',
        }),
        _kpiCard({
            label: 'Pendiente confirmar', value: counts.waitingConfirmation,
            help: 'entregadas; falta tu OK',
            variant: counts.waitingConfirmation > 0 ? 'is-success' : '',
        }),
        _kpiCard({ label: 'Cerradas', value: counts.closed,
                   help: 'flujo completo' }),
        _kpiCard({
            label: 'Rechazadas / anuladas', value: counts.rejectedOrCancelled,
            variant: counts.rejectedOrCancelled > 0 ? 'is-danger' : '',
        }),
    ]);

    return el('div', {}, [greeting, grid]);
}


function _renderMyRequestsTable(rows, api) {
    if (rows.length === 0) {
        return el('div', { class: 'sup-card' }, [
            el('header', { class: 'sup-card-header' }, [
                el('h3', { text: 'Aún no has creado solicitudes' }),
            ]),
            el('div', { class: 'sup-card-padded' }, [
                el('p', {
                    class: 'sup-muted',
                    text: 'Usa el botón "Nueva solicitud" arriba para crear la primera.',
                }),
            ]),
        ]);
    }

    const thead = el('thead', {}, [el('tr', {}, [
        el('th', { text: 'Código' }),
        el('th', { text: 'Estado' }),
        el('th', { text: 'Líneas' }),
        el('th', { text: 'Solicitado' }),
        el('th', { text: 'Procesado' }),
        el('th', { text: 'Entregado' }),
        el('th', { text: 'Cerrado' }),
        el('th', { text: '' }),
    ])]);

    // Re-mount the route after a transition so KPIs and the table stay in
    // sync. Cheap because listRequests({}) returns a single page.
    const refresh = () => window.dispatchEvent(new HashChangeEvent('hashchange'));

    const tbody = el('tbody', {}, rows.map(row =>
        el('tr', {}, [
            el('td', { text: row.code }),
            el('td', {}, [statusBadge(row.status)]),
            el('td', { text: '—' }),
            el('td', { text: formatDate(row.requested_at, true) }),
            el('td', { text: row.processed_at ? formatDate(row.processed_at, true) : '—' }),
            el('td', { text: row.delivered_at ? formatDate(row.delivered_at, true) : '—' }),
            el('td', { text: row.closed_at ? formatDate(row.closed_at, true) : '—' }),
            el('td', { class: 'sup-row-actions' }, [
                el('button', {
                    class: 'sup-icon-btn',
                    title: 'Ver detalle e ítems pedidos',
                    html: '<i class="fa-solid fa-magnifying-glass"></i>',
                    onClick: () => openRequestDetailModal({
                        api, requestId: row.id, onChange: refresh,
                    }),
                }),
            ]),
        ]),
    ));

    return _section('Mis solicitudes', el('div', { class: 'sup-table-wrap' }, [
        el('table', { class: 'sup-table' }, [thead, tbody]),
    ]), rows.length);
}
