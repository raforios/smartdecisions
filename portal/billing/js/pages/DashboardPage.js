/**
 * DashboardPage — lo que el mostrador necesita ver al abrir.
 *
 * Cuatro preguntas y nada más: cuánto vendí, qué me dejó, qué está por vencer
 * y qué se me está acabando. El tablero del almacén contaba solicitudes; este
 * producto no las tiene y no hereda sus indicadores.
 */
import { BillingService, errorText } from '../services/BillingService.js';
import { escapeHtml, money, percent, shortDate, todayIso } from '../ui.js';

function kpi(label, value, foot) {
    return `<div class="card kpi">
        <span class="label">${escapeHtml(label)}</span>
        <span class="value">${value}</span>
        ${foot ? `<span class="foot">${foot}</span>` : ''}
    </div>`;
}

function expiryTable(rows, emptyText, showDays) {
    if (!rows.length) return `<p class="muted small">${escapeHtml(emptyText)}</p>`;
    return `<div class="table-scroll"><table class="data-table">
        <thead><tr><th>Producto</th><th>Lote</th><th>Vence</th>
                   <th class="num">Quedan</th><th class="num">Al costo</th></tr></thead>
        <tbody>${rows.map((row) => `
            <tr>
                <td><strong>${escapeHtml(row.description)}</strong>
                    <span class="muted">${escapeHtml(row.sku)}</span></td>
                <td>${row.lot_code ? escapeHtml(row.lot_code) : '<span class="muted">—</span>'}</td>
                <td class="${showDays ? 'warn' : 'danger'}">
                    ${shortDate(row.expiry_date)}
                    ${showDays ? `<span class="muted">en ${row.days_left} días</span>`
                               : `<span class="muted">hace ${-row.days_left} días</span>`}</td>
                <td class="num">${money(row.quantity_remaining, 0)}</td>
                <td class="num">${money(row.value_at_cost)}</td>
            </tr>`).join('')}</tbody>
    </table></div>`;
}

/**
 * Pinta el tablero del rango elegido, hoy por defecto.
 *
 * @param {HTMLElement} host Dónde se monta la sección.
 */
export async function mountDashboard(host) {
    host.innerHTML = `
        <header class="page-head">
            <h2>Tablero</h2>
            <p class="muted">Qué se vendió, qué dejó, qué está por vencer y qué se acaba.</p>
        </header>
        <section class="card">
            <div class="field-row">
                <label class="field"><span>Desde</span>
                    <input type="date" id="from" value="${todayIso()}"></label>
                <label class="field"><span>Hasta</span>
                    <input type="date" id="to" value="${todayIso()}"></label>
                <div class="field" style="align-self: end">
                    <button class="btn btn-secondary" id="reload">Ver</button>
                </div>
            </div>
        </section>
        <div id="board"><p class="muted">Cargando…</p></div>`;

    async function load() {
        const board = host.querySelector('#board');
        try {
            const data = await BillingService.dashboard({
                date_from: host.querySelector('#from').value,
                date_to: host.querySelector('#to').value
            });

            board.innerHTML = `
                <div class="kpi-grid">
                    ${kpi('Vendido', `Bs ${money(data.sales_amount)}`,
                          `${data.sales_count} nota(s)` +
                          (data.cancelled_count ? ` · ${data.cancelled_count} anulada(s)` : ''))}
                    ${kpi('Margen', `Bs ${money(data.margin)}`,
                          data.margin_percent === null ? 'sin ventas'
                              : `${percent(data.margin_percent)} sobre lo cobrado`)}
                    ${kpi('Ticket promedio',
                          data.average_ticket === null ? '—' : `Bs ${money(data.average_ticket)}`,
                          `costo Bs ${money(data.sales_cost)}`)}
                    ${kpi('Capital en estantería', `Bs ${money(data.stock_value_at_cost)}`,
                          'al costo de cada lote')}
                </div>

                <div class="panel-grid">
                    <section class="card">
                        <h3>Por vencer</h3>
                        <p class="muted small">Lotes que vencen dentro de
                           ${data.expiry_alert_days} días: todavía se venden o se devuelven.</p>
                        ${expiryTable(data.expiring_soon, 'Nada por vencer en ese plazo.', true)}
                    </section>

                    <section class="card">
                        <h3>Vencidos</h3>
                        <p class="muted small">Tienen que salir del estante.</p>
                        ${expiryTable(data.expired, 'Nada vencido en estantería.', false)}
                    </section>

                    <section class="card">
                        <h3>Bajo mínimo</h3>
                        ${data.low_stock.length ? `
                            <div class="table-scroll"><table class="data-table">
                                <thead><tr><th>Producto</th><th class="num">Disponible</th>
                                           <th class="num">Mínimo</th></tr></thead>
                                <tbody>${data.low_stock.map((row) => `
                                    <tr>
                                        <td><strong>${escapeHtml(row.description)}</strong>
                                            <span class="muted">${escapeHtml(row.sku)}</span></td>
                                        <td class="num warn">${money(row.available_quantity, 0)}</td>
                                        <td class="num">${money(row.min_stock, 0)}</td>
                                    </tr>`).join('')}</tbody>
                            </table></div>`
                            : '<p class="muted small">Nada por debajo del mínimo.</p>'}
                    </section>

                    <section class="card">
                        <h3>Más vendidos</h3>
                        <p class="muted small">Por monto cobrado, no por cajas.</p>
                        ${data.top_products.length ? `
                            <div class="table-scroll"><table class="data-table">
                                <thead><tr><th>Producto</th><th class="num">Unidades</th>
                                           <th class="num">Importe</th></tr></thead>
                                <tbody>${data.top_products.map((row) => `
                                    <tr>
                                        <td><strong>${escapeHtml(row.description)}</strong>
                                            <span class="muted">${escapeHtml(row.sku)}</span></td>
                                        <td class="num">${money(row.quantity, 0)}</td>
                                        <td class="num">${money(row.amount)}</td>
                                    </tr>`).join('')}</tbody>
                            </table></div>`
                            : '<p class="muted small">No hubo ventas en el rango.</p>'}
                    </section>
                </div>`;
        } catch (error) {
            board.innerHTML = `<div class="card empty-state"><h3>No se pudo leer el tablero</h3>
                <p class="muted">${escapeHtml(errorText(error, 'El servicio no respondió.'))}</p></div>`;
        }
    }

    host.querySelector('#reload').addEventListener('click', load);
    await load();
}
