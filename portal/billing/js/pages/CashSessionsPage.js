/**
 * CashSessionsPage — every till of the merchant, for the manager.
 *
 * Reconciliation is daily: each till of the day is shown here with the
 * expected, the counted and the difference, and the till of someone who left
 * without closing it can be closed, with the reason written down.
 */
import { BillingService, errorText } from '../services/BillingService.js';
import { mountCloseForm, tillSummaryHtml } from './CashPage.js';
import { escapeHtml, money, shortDate, stamp, todayIso } from '../ui.js';

function statusChip(till) {
    if (till.status === 'CLOSED') return '<span class="chip chip-muted">Cerrada</span>';
    if (till.expired) return '<span class="chip chip-danger">Abierta de otro día</span>';
    return '<span class="chip chip-warn">Abierta</span>';
}

function differenceCell(till) {
    if (till.difference === null || till.difference === undefined) return '—';
    const tone = till.difference < 0 ? 'danger' : (till.difference > 0 ? 'warn' : 'ok');
    return `<span class="${tone}">${money(till.difference)}</span>`;
}

async function showDetail(host, sessionId) {
    const detail = host.querySelector('#till-detail');
    try {
        const till = await BillingService.getTill(sessionId);
        detail.innerHTML = `
            <section class="card">
                <h3>Caja de ${escapeHtml(till.user_email)} — ${shortDate(till.business_day)}</h3>
                <p class="muted small">${statusChip(till)}
                   ${till.closed_at ? ` Cerrada ${stamp(till.closed_at)} por
                       ${escapeHtml(till.closed_by)}.` : ''}
                   ${till.note ? ` Observación: ${escapeHtml(till.note)}` : ''}</p>
            </section>
            ${tillSummaryHtml(till)}
            <div id="manager-close"></div>`;
        if (till.status === 'OPEN') {
            mountCloseForm(detail.querySelector('#manager-close'), till, {
                noteRequired: true,
                onClosed: async () => { await load(host); await showDetail(host, sessionId); }
            });
        }
        detail.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (error) {
        detail.innerHTML = `<div class="card empty-state"><h3>No se pudo abrir la caja</h3>
            <p class="muted">${escapeHtml(errorText(error, 'El servicio no respondió.'))}</p></div>`;
    }
}

async function load(host) {
    const holder = host.querySelector('#tills');
    try {
        const page = await BillingService.listTills({
            date_from: host.querySelector('#from').value,
            date_to: host.querySelector('#to').value,
            user_email: host.querySelector('#user').value.trim() || null
        });
        holder.innerHTML = page.items.length ? `
            <div class="table-scroll"><table class="data-table">
                <thead><tr><th>Usuario</th><th>Día</th><th>Estado</th>
                           <th class="num">Ventas</th><th class="num">Esperado</th>
                           <th class="num">Contado</th><th class="num">Diferencia</th>
                           <th></th></tr></thead>
                <tbody>${page.items.map((till) => `
                    <tr>
                        <td>${escapeHtml(till.user_email)}</td>
                        <td>${shortDate(till.business_day)}</td>
                        <td>${statusChip(till)}</td>
                        <td class="num">${money(till.income_total)}</td>
                        <td class="num">${money(till.expected_cash)}</td>
                        <td class="num">${money(till.counted_cash)}</td>
                        <td class="num">${differenceCell(till)}</td>
                        <td><button class="btn btn-ghost btn-small open-till"
                                    data-id="${escapeHtml(till.session_id)}">Ver</button></td>
                    </tr>`).join('')}</tbody>
            </table></div>`
            : '<p class="muted small">No hay cajas en ese rango.</p>';
    } catch (error) {
        holder.innerHTML = `<p class="muted small">${
            escapeHtml(errorText(error, 'No se pudo leer las cajas.'))}</p>`;
    }
}

/**
 * Paints the list of tills and wires it.
 *
 * @param {HTMLElement} host Where the section mounts.
 */
export async function mountCashSessions(host) {
    host.innerHTML = `
        <header class="page-head">
            <h2>Cajas</h2>
            <p class="muted">Cada caja es de un usuario y de un día: lo esperado, lo
               contado y la diferencia.</p>
        </header>
        <section class="card">
            <div class="field-row">
                <label class="field"><span>Desde</span>
                    <input type="date" id="from" value="${todayIso()}"></label>
                <label class="field"><span>Hasta</span>
                    <input type="date" id="to" value="${todayIso()}"></label>
                <label class="field"><span>Usuario (opcional)</span>
                    <input type="email" id="user" placeholder="correo@comercio"></label>
                <div class="field" style="align-self: end">
                    <button class="btn btn-secondary" id="reload">Ver</button>
                </div>
            </div>
            <div id="tills"><p class="muted">Cargando…</p></div>
        </section>
        <div id="till-detail"></div>`;

    host.querySelector('#reload').addEventListener('click', () => load(host));
    host.querySelector('#tills').addEventListener('click', (event) => {
        const button = event.target.closest('.open-till');
        if (button) showDetail(host, button.dataset.id);
    });
    await load(host);
}
