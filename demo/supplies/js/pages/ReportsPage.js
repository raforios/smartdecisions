/**
 * Reports page.
 *
 * Three tabs:
 *   - Stock bajo: items at/below the minimum, with the deficit precomputed.
 *   - Reposiciones: replenishments report bounded by date range.
 *   - Solicitudes: requests report bounded by date and status.
 */
import {
    clear,
    el,
    formatDate,
    formatNumber,
    showToast,
    statusBadge,
} from '../ui.js';

const TABS = [
    { key: 'low', label: 'Stock bajo mínimo' },
    { key: 'reps', label: 'Reposiciones' },
    { key: 'reqs', label: 'Solicitudes' },
];

const REQUEST_STATUSES = [
    { value: '', label: 'Todos' },
    { value: 'CREATED', label: 'Creadas' },
    { value: 'IN_PROCESS', label: 'En proceso' },
    { value: 'DELIVERED', label: 'Entregadas' },
    { value: 'CLOSED', label: 'Cerradas' },
    { value: 'REJECTED', label: 'Rechazadas' },
    { value: 'CANCELLED', label: 'Anuladas' },
];

export async function mountReports({ host, actions, api }) {
    clear(host);
    actions.innerHTML = '';

    const tabsEl = el('div', { class: 'sup-tabs' });
    const panelEl = el('div', {});
    host.appendChild(tabsEl);
    host.appendChild(panelEl);

    const state = { api, actions, host: panelEl };

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
        if (key === 'low') return _renderLowStock(state);
        if (key === 'reps') return _renderReplenishmentsReport(state);
        return _renderRequestsReport(state);
    }

    _activate('low');
}

async function _renderLowStock(state) {
    state.actions.innerHTML = '';
    clear(state.host);
    state.host.appendChild(el('p', { class: 'sup-placeholder', text: 'Cargando…' }));
    try {
        const rows = await state.api.reportLowStock();
        clear(state.host);
        if (rows.length === 0) {
            state.host.appendChild(el('div', {
                class: 'sup-card sup-card-padded sup-muted',
                text: 'Ningún ítem está bajo el mínimo. Todo en orden.',
            }));
            return;
        }
        const thead = el('thead', {}, [el('tr', {}, [
            el('th', { text: 'Código' }),
            el('th', { text: 'Nombre' }),
            el('th', { text: 'Stock' }),
            el('th', { text: 'Mínimo' }),
            el('th', { text: 'Déficit' }),
        ])]);
        const tbody = el('tbody', {}, rows.map(r => el('tr', {}, [
            el('td', { text: r.item_code }),
            el('td', { text: r.item_name }),
            el('td', { text: formatNumber(r.current_stock) }),
            el('td', { text: formatNumber(r.min_stock) }),
            el('td', {}, [el('span', {
                class: 'sup-badge sup-badge-rejected', text: formatNumber(r.deficit),
            })]),
        ])));
        state.host.appendChild(el('div', { class: 'sup-table-wrap' }, [
            el('table', { class: 'sup-table' }, [thead, tbody]),
        ]));
    } catch (err) {
        clear(state.host);
        state.host.appendChild(el('p', { class: 'sup-form-error', text: err.message }));
        showToast(err.message, 'error');
    }
}

async function _renderReplenishmentsReport(state) {
    state.actions.innerHTML = '';
    clear(state.host);
    const filters = _dateFilters(reload);
    const tableHost = el('div', {});
    state.host.appendChild(filters.el);
    state.host.appendChild(tableHost);

    async function reload() {
        clear(tableHost);
        tableHost.appendChild(el('p', { class: 'sup-placeholder', text: 'Cargando…' }));
        try {
            const params = {};
            if (filters.values.from) params.date_from = `${filters.values.from}T00:00:00`;
            if (filters.values.to) params.date_to = `${filters.values.to}T23:59:59`;
            const rows = await state.api.reportReplenishments(params);
            clear(tableHost);
            if (rows.length === 0) {
                tableHost.appendChild(el('div', { class: 'sup-empty', text: 'Sin reposiciones en el rango.' }));
                return;
            }
            const thead = el('thead', {}, [el('tr', {}, [
                el('th', { text: 'Código' }),
                el('th', { text: 'Ítem' }),
                el('th', { text: 'Solicitado' }),
                el('th', { text: 'Recibido' }),
                el('th', { text: 'Estado' }),
                el('th', { text: 'Creado' }),
                el('th', { text: 'Completado' }),
            ])]);
            const tbody = el('tbody', {}, rows.map(r => el('tr', {}, [
                el('td', { text: r.code }),
                el('td', { text: r.item_code }),
                el('td', { text: formatNumber(r.requested_qty) }),
                el('td', { text: formatNumber(r.received_qty) }),
                el('td', {}, [statusBadge(r.status)]),
                el('td', { text: formatDate(r.created_at, true) }),
                el('td', { text: r.completed_at ? formatDate(r.completed_at, true) : '—' }),
            ])));
            tableHost.appendChild(el('div', { class: 'sup-table-wrap' }, [
                el('table', { class: 'sup-table' }, [thead, tbody]),
            ]));
        } catch (err) {
            clear(tableHost);
            tableHost.appendChild(el('p', { class: 'sup-form-error', text: err.message }));
        }
    }

    reload();
}

async function _renderRequestsReport(state) {
    state.actions.innerHTML = '';
    clear(state.host);
    const filters = _dateFilters(reload);
    const statusSel = el('select', {});
    REQUEST_STATUSES.forEach(o => statusSel.appendChild(el('option', { value: o.value, text: o.label })));
    statusSel.onchange = reload;
    filters.el.appendChild(el('label', { class: 'sup-field' }, [
        el('span', { text: 'Estado' }), statusSel,
    ]));

    const tableHost = el('div', {});
    state.host.appendChild(filters.el);
    state.host.appendChild(tableHost);

    async function reload() {
        clear(tableHost);
        tableHost.appendChild(el('p', { class: 'sup-placeholder', text: 'Cargando…' }));
        try {
            const params = {};
            if (filters.values.from) params.date_from = `${filters.values.from}T00:00:00`;
            if (filters.values.to) params.date_to = `${filters.values.to}T23:59:59`;
            if (statusSel.value) params.status = statusSel.value;
            const rows = await state.api.reportRequests(params);
            clear(tableHost);
            if (rows.length === 0) {
                tableHost.appendChild(el('div', { class: 'sup-empty', text: 'Sin solicitudes.' }));
                return;
            }
            const thead = el('thead', {}, [el('tr', {}, [
                el('th', { text: 'Código' }),
                el('th', { text: 'Solicitante' }),
                el('th', { text: 'Items' }),
                el('th', { text: 'Estado' }),
                el('th', { text: 'Solicitado' }),
                el('th', { text: 'Cerrado' }),
            ])]);
            const tbody = el('tbody', {}, rows.map(r => el('tr', {}, [
                el('td', { text: r.code }),
                el('td', { text: r.requester_email }),
                el('td', { text: formatNumber(r.total_items, 0) }),
                el('td', {}, [statusBadge(r.status)]),
                el('td', { text: formatDate(r.requested_at, true) }),
                el('td', { text: r.closed_at ? formatDate(r.closed_at, true) : '—' }),
            ])));
            tableHost.appendChild(el('div', { class: 'sup-table-wrap' }, [
                el('table', { class: 'sup-table' }, [thead, tbody]),
            ]));
        } catch (err) {
            clear(tableHost);
            tableHost.appendChild(el('p', { class: 'sup-form-error', text: err.message }));
        }
    }

    reload();
}

function _dateFilters(onChange) {
    const values = { from: '', to: '' };
    const wrap = el('div', { class: 'sup-filters' });
    const fromIn = el('input', { type: 'date' });
    fromIn.onchange = () => { values.from = fromIn.value; onChange(); };
    const toIn = el('input', { type: 'date' });
    toIn.onchange = () => { values.to = toIn.value; onChange(); };
    wrap.appendChild(el('label', { class: 'sup-field' }, [el('span', { text: 'Desde' }), fromIn]));
    wrap.appendChild(el('label', { class: 'sup-field' }, [el('span', { text: 'Hasta' }), toIn]));
    return { el: wrap, values };
}
