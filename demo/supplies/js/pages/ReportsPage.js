/**
 * Reports page.
 *
 * Three tabs:
 *   - Stock bajo: items at/below the minimum, with the deficit precomputed.
 *   - Notas de Ingreso: entries report bounded by date range.
 *   - Solicitudes: requests report bounded by date and status.
 */
import {
    clear,
    collapsible,
    el,
    formatDate,
    formatMoney,
    formatNumber,
    itemPicker,
    showToast,
    statusBadge,
} from '../ui.js';

const TABS = [
    { key: 'physical', label: 'Inventario Físico Valorado' },
    { key: 'stock', label: 'Stock Existente' },
    { key: 'inout', label: 'Entradas/Salidas por Cuenta' },
    { key: 'kardexv', label: 'Kardex Valorado' },
    { key: 'outflow', label: 'Estadísticas de Salida' },
    { key: 'low', label: 'Stock bajo mínimo' },
    { key: 'entries', label: 'Notas de Ingreso' },
    { key: 'reqs', label: 'Solicitudes' },
];

const ENTRY_TYPE_LABEL = {
    COMPRA: 'Compra',
    DONACION_TRANSFERENCIA: 'Donación y/o Transferencia',
    REINGRESO: 'Reingreso',
};

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
        if (key === 'physical') return _renderPhysicalValued(state);
        if (key === 'stock') return _renderStockOnHand(state);
        if (key === 'inout') return _renderInOutByGroup(state);
        if (key === 'kardexv') return _renderKardexValued(state);
        if (key === 'outflow') return _renderOutflow(state);
        if (key === 'low') return _renderLowStock(state);
        if (key === 'entries') return _renderEntriesReport(state);
        return _renderRequestsReport(state);
    }

    _activate('physical');
}

// --------------------------------------------------------------------- //
// KPIs and charts                                                        //
// --------------------------------------------------------------------- //
// Palette aligned with the institutional CSS variables.
const CHART_COLORS = ['#1f4f8b', '#0fa3a3', '#a96a00', '#166f54', '#2c5cb1',
                      '#b3261e', '#5d6577', '#8b93a4', '#173d6c', '#0b7c7c'];
let _chartSeq = 0;

/**
 * Row of headline figures. A report that only prints tables makes the reader
 * do the arithmetic; these answer the obvious questions up front.
 */
function _kpiRow(cards) {
    return el('div', { class: 'sup-kpi-grid' }, cards.map(card => el('div', {
        class: 'sup-kpi',
    }, [
        el('p', { class: 'sup-kpi-label', text: card.label }),
        el('p', { class: 'sup-kpi-value', text: card.value }),
        card.help ? el('p', { class: 'sup-kpi-help', text: card.help }) : null,
    ])));
}

/**
 * Chart card. Returns the node immediately and instantiates the chart once the
 * canvas is in the document, which Chart.js requires to measure itself.
 */
function _chartCard(title, config) {
    _chartSeq += 1;
    const canvasId = `sup-chart-${_chartSeq}`;
    const canvas = el('canvas', { id: canvasId });
    const card = el('div', { class: 'sup-card sup-card-padded sup-chart-card' }, [
        el('h3', { class: 'sup-chart-title', text: title }),
        canvas,
    ]);
    // The node is appended by the caller; defer until it is on screen.
    setTimeout(() => {
        if (!window.Chart || !document.getElementById(canvasId)) return;
        new window.Chart(canvas, config);
    }, 0);
    return card;
}

function _barChart(title, labels, values, label) {
    return _chartCard(title, {
        type: 'bar',
        data: {
            labels,
            datasets: [{ label, data: values, backgroundColor: CHART_COLORS[0] }],
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            plugins: { legend: { display: false } },
        },
    });
}

function _doughnutChart(title, labels, values) {
    return _chartCard(title, {
        type: 'doughnut',
        data: { labels, datasets: [{ data: values, backgroundColor: CHART_COLORS }] },
        options: { responsive: true, plugins: { legend: { position: 'right' } } },
    });
}

function _chartGrid(children) {
    return el('div', { class: 'sup-chart-grid' }, children.filter(Boolean));
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
        const box = collapsible({
            title: 'Ítems bajo el mínimo',
            subtitle: `${rows.length} ítem(s)`,
            stateKey: 'reports.low-stock',
        });
        box.body.appendChild(el('div', { class: 'sup-table-wrap' }, [
            el('table', { class: 'sup-table' }, [thead, tbody]),
        ]));
        state.host.appendChild(box.section);
    } catch (err) {
        clear(state.host);
        state.host.appendChild(el('p', { class: 'sup-form-error', text: err.message }));
        showToast(err.message, 'error');
    }
}

async function _renderEntriesReport(state) {
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
            const rows = await state.api.reportEntries(params);
            clear(tableHost);
            if (rows.length === 0) {
                tableHost.appendChild(el('div', { class: 'sup-empty', text: 'Sin notas de ingreso en el rango.' }));
                return;
            }
            const thead = el('thead', {}, [el('tr', {}, [
                el('th', { text: 'Código' }),
                el('th', { text: 'Tipo' }),
                el('th', { text: 'Proveedor' }),
                el('th', { text: 'Líneas' }),
                el('th', { text: 'Subtotal' }),
                el('th', { text: 'Descuento' }),
                el('th', { text: 'Total' }),
                el('th', { text: 'Fecha' }),
            ])]);
            const tbody = el('tbody', {}, rows.map(r => el('tr', {}, [
                el('td', { text: r.code }),
                el('td', { text: ENTRY_TYPE_LABEL[r.entry_type] || r.entry_type }),
                el('td', { text: r.supplier || '—' }),
                el('td', { text: formatNumber(r.total_lines, 0) }),
                el('td', { text: formatMoney(r.subtotal) }),
                el('td', { text: formatMoney(r.discount) }),
                el('td', { text: formatMoney(r.total) }),
                el('td', { text: formatDate(r.created_at, true) }),
            ])));
            const box = collapsible({
                title: 'Notas de Ingreso',
                subtitle: `${rows.length} nota(s)`,
                stateKey: 'reports.entries',
            });
            box.body.appendChild(el('div', { class: 'sup-table-wrap' }, [
                el('table', { class: 'sup-table' }, [thead, tbody]),
            ]));
            tableHost.appendChild(box.section);
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
            const box = collapsible({
                title: 'Solicitudes',
                subtitle: `${rows.length} solicitud(es)`,
                stateKey: 'reports.requests',
            });
            box.body.appendChild(el('div', { class: 'sup-table-wrap' }, [
                el('table', { class: 'sup-table' }, [thead, tbody]),
            ]));
            tableHost.appendChild(box.section);
        } catch (err) {
            clear(tableHost);
            tableHost.appendChild(el('p', { class: 'sup-form-error', text: err.message }));
        }
    }

    reload();
}

// --------------------------------------------------------------------- //
// Valued warehouse reports                                               //
// --------------------------------------------------------------------- //
async function _renderPhysicalValued(state) {
    const { filters, group, zero, container } = await _reportShell(state, {
        title: 'Inventario General Físico Valorado', withGroup: true, withZero: true, reload,
    });

    async function reload() {
        const params = { ..._rangeParams(filters, group), include_zero: zero.value() };
        await _withData(container, () => state.api.reportPhysicalValued(params), rep => {
            if (rep.groups.length === 0) return el('div', { class: 'sup-empty', text: 'Sin datos.' });
            const wrap = el('div', { class: 'sup-stack' });
            rep.groups.forEach(g => wrap.appendChild(_groupSection(g, 'physical', _table(
                ['Código', 'Detalle', 'Unidad', 'F.Inicio', 'F.Ingreso', 'F.Agrupado',
                 'F.Egreso', 'F.Final', 'P.Unit', 'V.Inicio', 'V.Ingreso', 'V.Agrupado',
                 'V.Egreso', 'V.Final'],
                g.items, r => [
                    r.item_code, r.item_name, r.unit,
                    _n(r.fisico_inicio), _n(r.fisico_ingreso), _n(r.fisico_agregado),
                    _n(r.fisico_egreso), _n(r.fisico_final), _m(r.precio_unitario),
                    _m(r.valorado_inicio), _m(r.valorado_ingreso), _m(r.valorado_agregado),
                    _m(r.valorado_egreso), _m(r.valorado_final),
                ]), g.valorado_final)));
            wrap.appendChild(el('h3', { text: 'Resumen por grupo' }));
            wrap.appendChild(_table(['Código', 'Grupo', 'Físico Final', 'Valorado Final'],
                rep.summary, s => [s.group_code, s.group_name, _n(s.fisico_final), _m(s.valorado_final)]));
            wrap.appendChild(el('p', { class: 'sup-total-strong',
                text: `Total valorado: ${formatMoney(rep.grand_total_valorado)}` }));

            const ranked = [...rep.summary].sort((a, b) => b.valorado_final - a.valorado_final);
            const top = ranked[0];
            const itemCount = rep.groups.reduce((acc, g) => acc + g.items.length, 0);
            const summary = el('div', {}, [
                _kpiRow([
                    { label: 'Total valorado', value: formatMoney(rep.grand_total_valorado),
                      help: 'Valor del inventario al cierre' },
                    { label: 'Grupos contables', value: String(rep.summary.length) },
                    { label: 'Ítems listados', value: String(itemCount) },
                    { label: 'Grupo de mayor valor', value: top ? top.group_code : '—',
                      help: top ? top.group_name : '' },
                ]),
                _chartGrid([
                    _barChart('Valorado por grupo contable (top 10)',
                        ranked.slice(0, 10).map(s => s.group_code),
                        ranked.slice(0, 10).map(s => Number(s.valorado_final)), 'Valorado'),
                    _doughnutChart('Participación del valor por grupo',
                        ranked.slice(0, 8).map(s => s.group_code),
                        ranked.slice(0, 8).map(s => Number(s.valorado_final))),
                ]),
            ]);
            return { summary, detail: wrap, title: 'Detalle por grupo contable',
                     subtitle: `${itemCount} ítem(s)` };
        });
    }
    reload();
}

async function _renderStockOnHand(state) {
    const { group, cutoff, zero, container } = await _reportShell(state, {
        title: 'Inventario con Stock Existente', withGroup: true, withDates: false,
        withCutoff: true, withZero: false, reload,
    });

    async function reload() {
        const params = { include_zero: zero.value() };
        if (group.value()) params.group_code = group.value();
        if (cutoff.value()) params.date_to = `${cutoff.value()}T23:59:59`;
        await _withData(container, () => state.api.reportStockOnHand(params), rep => {
            if (rep.groups.length === 0) return el('div', { class: 'sup-empty', text: 'Sin stock existente.' });
            const wrap = el('div', { class: 'sup-stack' });
            rep.groups.forEach(g => wrap.appendChild(_groupSection(g, 'stock', _table(
                ['Código', 'Detalle', 'Unidad', 'Saldo Existente', 'Precio Unitario',
                 'Total Valorado'],
                g.items, r => [r.item_code, r.item_name, r.unit,
                    _n(r.saldo_existente), _m(r.precio_unitario), _m(r.total_valorado)]),
                g.total_valorado)));
            wrap.appendChild(el('h3', { text: 'Resumen por grupo' }));
            wrap.appendChild(_table(['Código', 'Grupo', 'Saldo', 'Total Valorado'],
                rep.summary, s => [s.group_code, s.group_name, _n(s.saldo_existente), _m(s.total_valorado)]));
            wrap.appendChild(el('p', { class: 'sup-total-strong',
                text: `Total valorado: ${formatMoney(rep.grand_total_valorado)}` }));

            const items = rep.groups.flatMap(g => g.items);
            const byValue = [...items].sort((a, b) => b.total_valorado - a.total_valorado);
            const concentration = rep.grand_total_valorado > 0
                ? byValue.slice(0, 10).reduce((acc, i) => acc + Number(i.total_valorado), 0)
                  / Number(rep.grand_total_valorado) * 100
                : 0;
            const summary = el('div', {}, [
                _kpiRow([
                    { label: 'Total valorado', value: formatMoney(rep.grand_total_valorado) },
                    { label: 'Ítems con saldo', value: String(items.length) },
                    { label: 'Grupos con stock', value: String(rep.summary.length) },
                    { label: 'Peso del top 10', value: `${formatNumber(concentration, 1)}%`,
                      help: 'Del valor total del almacén' },
                ]),
                _chartGrid([
                    _barChart('Ítems de mayor valor en almacén (top 10)',
                        byValue.slice(0, 10).map(i => i.item_code),
                        byValue.slice(0, 10).map(i => Number(i.total_valorado)), 'Valorado'),
                    _doughnutChart('Valor por grupo contable',
                        rep.summary.slice(0, 8).map(s => s.group_code),
                        rep.summary.slice(0, 8).map(s => Number(s.total_valorado))),
                ]),
            ]);
            return { summary, detail: wrap, title: 'Detalle por grupo contable',
                     subtitle: `${items.length} ítem(s) con saldo` };
        });
    }
    reload();
}

async function _renderInOutByGroup(state) {
    const { filters, container } = await _reportShell(state, {
        title: 'Entradas y Salidas Valorado por Cuenta Contable', reload,
    });

    async function reload() {
        await _withData(container, () => state.api.reportInOutByGroup(_rangeParams(filters)), rep => {
            if (rep.rows.length === 0) return el('div', { class: 'sup-empty', text: 'Sin movimientos en el rango.' });
            const wrap = el('div', { class: 'sup-stack' });
            wrap.appendChild(_table(['Código', 'Cuenta contable', 'Ingresos', 'Salidas', 'Saldo'],
                rep.rows, r => [r.group_code, r.group_name, _m(r.ingresos), _m(r.salidas), _m(r.saldo)]));
            wrap.appendChild(el('p', { class: 'sup-total-strong',
                text: `Totales — Ingresos: ${formatMoney(rep.total_ingresos)} · `
                    + `Salidas: ${formatMoney(rep.total_salidas)} · Saldo: ${formatMoney(rep.total_saldo)}` }));

            const moved = rep.rows.filter(r => Number(r.ingresos) || Number(r.salidas));
            const topOut = [...moved].sort((a, b) => b.salidas - a.salidas)[0];
            const rotation = Number(rep.total_ingresos) > 0
                ? Number(rep.total_salidas) / Number(rep.total_ingresos) * 100 : 0;
            const summary = el('div', {}, [
                _kpiRow([
                    { label: 'Ingresos', value: formatMoney(rep.total_ingresos) },
                    { label: 'Salidas', value: formatMoney(rep.total_salidas) },
                    { label: 'Saldo del período', value: formatMoney(rep.total_saldo) },
                    { label: 'Rotación', value: `${formatNumber(rotation, 1)}%`,
                      help: 'Salidas sobre ingresos del período' },
                ]),
                _chartGrid([
                    _chartCard('Ingresos vs salidas por cuenta contable', {
                        type: 'bar',
                        data: {
                            labels: moved.map(r => r.group_code),
                            datasets: [
                                { label: 'Ingresos', data: moved.map(r => Number(r.ingresos)),
                                  backgroundColor: CHART_COLORS[0] },
                                { label: 'Salidas', data: moved.map(r => Number(r.salidas)),
                                  backgroundColor: CHART_COLORS[2] },
                            ],
                        },
                        options: { responsive: true, plugins: { legend: { position: 'bottom' } } },
                    }),
                    topOut ? _doughnutChart('Salidas por cuenta contable',
                        moved.map(r => r.group_code),
                        moved.map(r => Number(r.salidas))) : null,
                ]),
            ]);
            return { summary, detail: wrap, title: 'Detalle por cuenta contable',
                     subtitle: `${rep.rows.length} cuenta(s)` };
        });
    }
    reload();
}

async function _renderKardexValued(state) {
    const { filters, group, item, container } = await _reportShell(state, {
        title: 'Kardex de Control de Existencias — Físico y Valorado',
        withGroup: true, withItem: true, withSignatures: true, reload,
    });

    async function reload() {
        const params = _rangeParams(filters, group);
        if (item.value()) params.item_id = Number(item.value());
        await _withData(container, () => state.api.reportKardexValued(params), rep => {
            if (rep.items.length === 0) return el('div', { class: 'sup-empty', text: 'Sin movimientos.' });
            const wrap = el('div', { class: 'sup-stack' });
            rep.items.forEach(it => {
                wrap.appendChild(el('h3', { text: `${it.item_code} — ${it.item_name} (${it.unit})` }));
                wrap.appendChild(el('p', { class: 'sup-muted',
                    text: `Grupo: ${it.group_name} · Saldo inicial: ${formatNumber(it.saldo_inicial_qty)} `
                        + `(${formatMoney(it.saldo_inicial_val)})` }));
                wrap.appendChild(_table(
                    ['Fecha', 'Detalle', 'N° ingreso', 'Entrada', 'Salida', 'Saldo',
                     'P.Unit', 'Ent. Val', 'Sal. Val', 'Saldo Val'],
                    it.lines, l => [
                        formatDate(l.created_at, true), l.detail,
                        l.source_entry_id ? `#${l.source_entry_id}` : '—',
                        _n(l.entrada_qty), _n(l.salida_qty), _n(l.saldo_qty),
                        l.unit_cost != null ? _m(l.unit_cost) : '—',
                        _m(l.entrada_val), _m(l.salida_val), _m(l.saldo_val),
                    ]));
                wrap.appendChild(el('p', { class: 'sup-total-strong',
                    text: `Saldo final: ${formatNumber(it.saldo_final_qty)} (${formatMoney(it.saldo_final_val)})` }));
            });
            return wrap;
        });
    }
    reload();
}

async function _renderOutflow(state) {
    const { filters, container } = await _reportShell(state, {
        title: 'Estadísticas de Salida de Artículos', reload,
    });

    async function reload() {
        await _withData(container, () => state.api.reportOutflowStats(_rangeParams(filters)), rep => {
            if (rep.items.length === 0) return el('div', { class: 'sup-empty', text: 'Sin salidas en el rango.' });
            const wrap = el('div', { class: 'sup-stack' });
            rep.items.forEach(it => {
                wrap.appendChild(el('h3', {
                    text: `${it.item_code} — ${it.item_name} (${it.unit}) · Total salida: ${formatNumber(it.total_salida)}`,
                }));
                wrap.appendChild(_table(['Fecha', 'Destinatario', 'Solicitud', 'Cantidad'],
                    it.lines, l => [formatDate(l.created_at, true), l.recipient,
                        l.request_code || '—', _n(l.quantity)]));
            });
            wrap.appendChild(el('p', { class: 'sup-total-strong',
                text: `Total general de salida: ${formatNumber(rep.grand_total_salida)}` }));

            const ranked = [...rep.items].sort((a, b) => b.total_salida - a.total_salida);
            const deliveries = rep.items.reduce((acc, it) => acc + it.lines.length, 0);
            const recipients = new Set(
                rep.items.flatMap(it => it.lines.map(l => l.recipient))).size;
            const summary = el('div', {}, [
                _kpiRow([
                    { label: 'Unidades entregadas', value: formatNumber(rep.grand_total_salida) },
                    { label: 'Ítems con salida', value: String(rep.items.length) },
                    { label: 'Entregas registradas', value: String(deliveries) },
                    { label: 'Destinatarios distintos', value: String(recipients) },
                ]),
                _chartGrid([
                    _barChart('Artículos más solicitados (top 10)',
                        ranked.slice(0, 10).map(i => i.item_code),
                        ranked.slice(0, 10).map(i => Number(i.total_salida)), 'Unidades'),
                ]),
            ]);
            return { summary, detail: wrap, title: 'Detalle de salidas por artículo',
                     subtitle: `${rep.items.length} artículo(s)` };
        });
    }
    reload();
}

// --------------------------------------------------------------------- //
// Report helpers                                                         //
// --------------------------------------------------------------------- //
async function _reportShell(state, options) {
    const {
        title, reload,
        withDates = true, withGroup = false,
        withItem = false, withCutoff = false, withZero = null,
        withSignatures = false,
    } = options;

    state.actions.innerHTML = '';
    clear(state.host);
    const bar = el('div', { class: 'sup-filters' });
    const filters = withDates ? _dateFilters(reload) : null;
    if (filters) bar.appendChild(filters.el);
    const cutoff = withCutoff ? _cutoffDate(reload) : null;
    if (cutoff) bar.appendChild(cutoff.el);
    const group = withGroup ? await _groupSelect(state, reload) : null;
    if (group) bar.appendChild(group.el);
    const item = withItem ? await _itemSelect(state, reload) : null;
    if (item) bar.appendChild(item.el);
    const zero = withZero === null ? null : _zeroToggle(reload, withZero);
    if (zero) bar.appendChild(zero.el);

    const container = el('div', {});
    state.host.appendChild(bar);
    state.host.appendChild(container);

    state.actions.appendChild(el('button', {
        class: 'sup-btn sup-btn-ghost',
        html: '<i class="fa-solid fa-print"></i> Imprimir / PDF',
        onClick: () => _printWindow(title, container, { withSignatures }),
    }));
    return { filters, group, item, cutoff, zero, container };
}

/**
 * The legacy "CON REGISTROS 0 / SIN REGISTROS 0" switch. Each report passes
 * its own default because listing empty items makes sense for a full
 * inventory and not for a stock-on-hand snapshot.
 */
function _zeroToggle(onChange, defaultChecked) {
    const input = el('input', { type: 'checkbox' });
    input.checked = defaultChecked;
    input.onchange = onChange;
    return {
        el: el('label', { class: 'sup-field sup-field-check' }, [
            input, el('span', { text: 'Incluir registros en 0' }),
        ]),
        value: () => input.checked,
    };
}

/**
 * A stock snapshot has one cut-off date, not a range: it answers "how much was
 * there on this day". Left empty it reports the live stock.
 */
function _cutoffDate(onChange) {
    const input = el('input', { type: 'date' });
    input.onchange = onChange;
    return {
        el: el('label', { class: 'sup-field' }, [el('span', { text: 'Stock al' }), input]),
        value: () => input.value,
    };
}

async function _itemSelect(state, onChange) {
    if (!state.items) {
        state.items = await state.api.listItems({ limit: 500 });
    }
    const picker = itemPicker({
        items: state.items,
        placeholder: 'Todos los ítems — escribe para filtrar…',
        onSelect: onChange,
    });
    return {
        el: el('label', { class: 'sup-field' }, [el('span', { text: 'Ítem' }), picker.el]),
        value: () => picker.value() || '',
    };
}

async function _groupSelect(state, onChange) {
    if (!state.categories) {
        state.categories = await state.api.listCategories({ limit: 500 });
    }
    const sel = el('select', {});
    sel.appendChild(el('option', { value: '', text: 'Todos los grupos' }));
    state.categories.forEach(c => sel.appendChild(el('option', { value: c.code, text: `${c.code} — ${c.name}` })));
    sel.onchange = onChange;
    return {
        el: el('label', { class: 'sup-field' }, [el('span', { text: 'Grupo contable' }), sel]),
        value: () => sel.value,
    };
}

function _rangeParams(filters, group) {
    const params = {};
    if (filters?.values.from) params.date_from = `${filters.values.from}T00:00:00`;
    if (filters?.values.to) params.date_to = `${filters.values.to}T23:59:59`;
    if (group?.value()) params.group_code = group.value();
    return params;
}

async function _withData(container, loader, render) {
    clear(container);
    container.appendChild(el('p', { class: 'sup-placeholder', text: 'Generando reporte…' }));
    try {
        const data = await loader();
        const result = render(data);
        clear(container);
        if (result && result.detail) {
            if (result.summary) container.appendChild(result.summary);
            const box = collapsible({
                title: result.title || 'Detalle del reporte',
                subtitle: result.subtitle || '',
                stateKey: `reports.detail.${result.title || 'generic'}`,
            });
            box.body.appendChild(result.detail);
            container.appendChild(box.section);
        } else {
            container.appendChild(result);
        }
    } catch (err) {
        clear(container);
        container.appendChild(el('p', { class: 'sup-form-error', text: err.message }));
    }
}

function _table(headers, rows, mapper) {
    const thead = el('thead', {}, [el('tr', {}, headers.map(h => el('th', { text: h })))]);
    const tbody = el('tbody', {}, rows.map(r =>
        el('tr', {}, mapper(r).map(cell => el('td', { text: cell ?? '—' })))));
    return el('div', { class: 'sup-table-wrap' }, [el('table', { class: 'sup-table' }, [thead, tbody])]);
}

/**
 * One accounting group inside a valued report.
 *
 * A ministry inventory has 19 groups and 380+ articles: rendering them all
 * expanded buries the report, so each group is its own collapsed section
 * showing its code, name and total. The subtotal stays visible in the header
 * so the reader can scan the groups without opening any of them.
 */
function _groupSection(group, scope, table, total) {
    const box = collapsible({
        title: `${group.group_code} — ${group.group_name}`,
        subtitle: `${group.items.length} ítem(s) · ${_m(total)}`,
        stateKey: `reports.${scope}.group.${group.group_code}`,
    });
    box.body.appendChild(table);
    return box.section;
}


function _n(value) {
    return value == null ? '—' : formatNumber(value);
}

// Valued columns are money: two decimals always, so a column of amounts lines up.
function _m(value) {
    return value == null ? '—' : formatMoney(value);
}

function _printWindow(title, node, { withSignatures = false } = {}) {
    const win = window.open('', '_blank', 'width=1024,height=720');
    if (!win) {
        showToast('Permite las ventanas emergentes para imprimir.', 'warning');
        return;
    }
    const styles = 'body{font-family:Arial,Helvetica,sans-serif;font-size:12px;color:#111;padding:24px}'
        + 'h1{font-size:16px;text-align:center;margin:0 0 12px}h3{font-size:13px;margin:16px 0 4px}'
        + 'p{margin:4px 0}.sup-muted{color:#555}.sup-total-strong{font-weight:bold}'
        + 'table{width:100%;border-collapse:collapse;margin-bottom:8px}'
        + 'th,td{border:1px solid #999;padding:3px 6px;text-align:left;font-size:11px}th{background:#eee}'
        // The report may be printed while its section is collapsed on screen.
        + '.sup-collapsible-body{display:block!important}'
        + '.doc-signatures{display:flex;justify-content:space-around;gap:24px;margin-top:60px}'
        + '.doc-sign{flex:1;text-align:center;border-top:1px solid #000;padding-top:4px;'
        + 'font-size:10px;font-weight:bold}';

    // The valued kardex is signed by the warehouse and by administration, as
    // on the NSIAF form it replaces.
    const signatures = withSignatures
        ? '<div class="doc-signatures">'
          + '<div class="doc-sign">ENCARGADO DE ALMACENES Y SERVICIOS GENERALES</div>'
          + '<div class="doc-sign">JEFE ADMINISTRATIVO Y RECURSOS HUMANOS</div>'
          + '</div>'
        : '';
    // Same masthead as the signed forms: the printed report leaves the office.
    const head = '<p style="text-align:center;margin:0;font-weight:bold">'
        + 'MINISTERIO DE MINERÍA Y METALURGIA</p>'
        + `<h1>${title}</h1>`
        + '<p style="text-align:center;margin:0 0 14px">(Expresado en Bolivianos)</p>';
    win.document.write(`<!DOCTYPE html><html><head><meta charset="utf-8"><title>${title}</title>`
        + `<style>${styles}</style></head><body>${head}${node.innerHTML}`
        + `${signatures}</body></html>`);
    win.document.close();
    win.focus();
    setTimeout(() => win.print(), 300);
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
