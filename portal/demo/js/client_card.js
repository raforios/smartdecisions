'use strict';

/**
 * Clientes › Ficha — everything about one client in one place and the
 * timeline of its invoices and payments, which is the follow-up of what it
 * owes. What is owed and the totals read at today's rate; each month, at its
 * close; each invoice and payment, as recorded.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.isAuthenticated()) return;
    const { qs, toast } = window.SD_UI;
    const M = window.SD_MONEY;
    const BASE = `${window.SD_CONFIG.ANALYTICS_URL}/v1/analytics`;
    const TERMS = { CREDITO: 'Crédito', CONTADO: 'Contado' };
    const ERRORS = { CLIENT_NOT_FOUND: 'Ese cliente no está en tus datos de ventas.' };
    const state = { datasetId: null, card: null, currency: 'BOB', chart: null };

    const number = (value, decimals = 0) => (value == null ? '—'
        : Number(value).toLocaleString('es-BO', {
            minimumFractionDigits: decimals, maximumFractionDigits: decimals }));
    const day = (iso) => (iso ? iso.split('-').reverse().join('/') : '—');
    const escape = (text) => String(text == null ? '' : text)
        .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');

    function figure(label, value) {
        return `<div class="metric"><p class="metric-label">${label}</p>` +
            `<div class="metric-value">${value}</div></div>`;
    }

    /** One row of equal cards, like the analysis views. */
    function row(cards) {
        return `<div class="metric-row" style="--columns: ${cards.length}">${cards.join('')}</div>`;
    }

    function paintChart() {
        const card = state.card;
        if (!window.Chart || !card) return;
        if (state.chart) state.chart.destroy();
        state.chart = new window.Chart(qs('#clientMonths'), {
            type: 'bar',
            data: {
                labels: card.months.map((row) => row.month),
                datasets: [{ data: card.months.map((row) => M.pick(row.amount, state.currency)),
                             backgroundColor: '#0d1e4c' }]
            },
            options: { maintainAspectRatio: false, plugins: { legend: { display: false } } }
        });
    }

    function paint(card) {
        state.card = card;
        qs('#clientCard').hidden = false;
        qs('#clientName').textContent = card.name || card.client_id;
        qs('#clientIdentity').textContent = [card.seller && `Vendedor: ${card.seller}`,
            card.zone, card.city, card.channel].filter(Boolean).join(' · ');
        qs('#clientFigures').innerHTML = row([
            figure('Compró en total (hoy)', M.card(card.total)),
            figure('Compras', number(card.purchases)),
            figure('Ticket promedio (hoy)', M.card(card.average_ticket)),
            figure('Primera · última compra', `${day(card.first_purchase)} · ${day(card.last_purchase)}`),
            figure('Días sin comprar', number(card.days_since_last))
        ]);
        const owed = card.receivable || {};
        qs('#clientReceivable').innerHTML = owed.available ? row([
            figure('Te debe (hoy)', M.card(owed.balance)),
            figure('Vencido (hoy)', M.card(owed.overdue)),
            figure('Facturas abiertas', number(owed.open_invoices)),
            figure('Días del atraso mayor', number(owed.oldest_days_past_due)),
            figure('Línea de crédito', owed.credit_limit ? M.card(owed.credit_limit) : 'sin línea')
        ]) : '<p class="legend-hint">Sin ventas a crédito.</p>';
        qs('#clientProducts tbody').innerHTML = card.products.map((row) =>
            `<tr><td>${escape(row.product)}</td><td class="numeric">${number(row.quantity)}</td>` +
            `${M.cells(row.amount, 0)}</tr>`).join('');
        qs('#clientTimeline tbody').innerHTML = card.timeline.map((entry) => {
            const invoice = entry.kind === 'INVOICE';
            return `<tr><td>${day(entry.date)}</td>` +
                `<td>${invoice ? 'Factura' : 'Pago'}</td>` +
                `<td>${escape(entry.order_id)}</td>` +
                `<td>${invoice ? (TERMS[entry.terms] || escape(entry.terms)) : '—'}</td>` +
                `<td>${day(entry.due_date)}</td>` +
                `<td class="numeric">${number(entry.amount && entry.amount.bob, 2)}</td>` +
                `<td class="numeric">${invoice ? number(entry.paid && entry.paid.bob, 2) : '—'}</td>` +
                `<td class="numeric">${invoice ? number(entry.balance && entry.balance.bob, 2)
                    : '—'}</td></tr>`;
        }).join('') || '<tr class="empty-row"><td colspan="8">Sin facturas.</td></tr>';
        paintChart();
    }

    async function open(clientId) {
        const note = qs('#clientNote');
        note.textContent = 'Armando la ficha…';
        try {
            paint(await window.SD_API.get(`${BASE}/client/` +
                `${encodeURIComponent(state.datasetId)}/${encodeURIComponent(clientId)}`));
            note.textContent = '';
            history.replaceState(null, '', `?client=${encodeURIComponent(clientId)}`);
        } catch (error) {
            note.textContent = ERRORS[error && error.code] || (error && error.message) ||
                'No se pudo armar la ficha.';
            toast(note.textContent, 'error');
        }
    }

    async function load() {
        M.expandHeaders(document);
        state.datasetId = await window.SD_API.ensureDataset();
        if (!state.datasetId) {
            qs('#clientNote').textContent = 'Primero carga el archivo de ventas en Ventas.';
            return;
        }
        const list = await window.SD_API.get(
            `${BASE}/clients/${encodeURIComponent(state.datasetId)}`).catch(() => null);
        const clients = (list && list.clients) || [];
        qs('#clientOptions').innerHTML = clients.map((client) =>
            `<option value="${escape(client.client_id)}">${escape(client.name || '')}</option>`)
            .join('');
        const wanted = new URLSearchParams(location.search).get('client');
        if (wanted) {
            qs('#clientSearch').value = wanted;
            open(wanted);
        }
    }

    qs('#clientOpen').addEventListener('click', () => {
        const value = qs('#clientSearch').value.trim();
        if (value) open(value);
    });
    qs('#clientCurrency').addEventListener('change', (event) => {
        state.currency = event.target.value;
        paintChart();
    });
    load();
});
