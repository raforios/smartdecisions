'use strict';

/**
 * Cotización anticipada — what the official quotation of the next fortnight is
 * heading to, from the days the market has already quoted.
 *
 * This is not a projection: it is the running mean of the fortnight in
 * progress, built from the daily fixes the Ministry itself uses — LBMA AM for
 * gold, the LBMA fix for silver, LME cash for the base metals. When the
 * fortnight closes, that mean *is* the official price for the next one, so the
 * screen answers "¿a cuánto voy a liquidar?" two weeks before the resolution.
 *
 * Antimony, wolfram and bismuth have no free daily feed (Asian Metal is paid),
 * so they show their quotation in force and nothing else: an invented number
 * would be worse than an empty cell.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.isAuthenticated()) return;

    const { qs, toast, setButtonBusy } = window.SD_UI;
    const {
        market, CONFIDENCE_LABELS, SOURCE_LABELS, BASIS_LABELS,
        errorText, money, percent, changeClass, shortDate, escapeHtml, sparkline
    } = window.SD_MIN;

    // Only these roles may hit the sources on demand; everyone else reads what
    // the nightly run left. The service enforces it too — this only avoids
    // showing a button that would answer 403.
    const SYNC_ROLES = ['ADMIN', 'MANAGER'];

    const state = { estimate: null, rules: null, series: {} };

    /**
     * The Art. 227 scale of one mineral, read once and kept: nine rows that
     * only change when an administrator edits them.
     */
    async function rulesByMineral() {
        if (state.rules) return state.rules;
        try {
            const data = await market.rules();
            state.rules = {};
            data.rules.forEach((rule) => { state.rules[rule.mineral_id] = rule; });
        } catch (error) {
            // The scale explains the rate; without it the rate still stands.
            state.rules = {};
        }
        return state.rules;
    }

    function confidenceTag(row) {
        const label = CONFIDENCE_LABELS[row.confidence] || row.confidence;
        return `<span class="tag tag-${row.confidence}">${label}</span>`;
    }

    /**
     * The rate cell: the percentage and which part of the scale produced it.
     * A rate sitting on the cap does not move when the price moves, and that
     * is worth seeing before anyone builds a plan on the difference.
     */
    function rateCell(value, basis) {
        if (value === null || value === undefined) {
            return '<td class="num muted-cell">—</td>';
        }
        // `money`, not `percent`: an alícuota is a level, not a change, and the
        // leading + of a variation made 5 % read as "subió cinco".
        return `<td class="num">
            <span class="official-value">${money(value, 2)} %</span>
            ${basis ? `<span class="official-window">${BASIS_LABELS[basis] || basis}</span>` : ''}
        </td>`;
    }

    function daysCell(row) {
        if (!row.source) {
            return '<td class="num muted-cell">sin fuente</td>';
        }
        return `<td class="num">
            <span class="official-value">${row.days_quoted}</span>
            <span class="official-window">de ${row.calendar_days_elapsed} días corridos</span>
        </td>`;
    }

    function estimateRow(row) {
        const tr = document.createElement('tr');
        tr.className = 'mineral-row';
        const expandable = Boolean(row.source);
        tr.innerHTML = `
            <td>
                <button class="verify-toggle" type="button" ${expandable ? '' : 'disabled'}
                        aria-expanded="false" data-mineral="${escapeHtml(row.mineral_id)}">
                    <span class="caret">▸</span>${escapeHtml(row.name)}</button>
                ${row.unit ? `<span class="unit">${escapeHtml(row.unit)}</span>` : ''}
                ${row.source
                    ? `<span class="source-chip">${SOURCE_LABELS[row.source] || row.source}</span>`
                    : '<span class="source-chip muted">informe quincenal</span>'}
            </td>
            <td class="num">${money(row.previous_official, 4)}</td>
            <td class="num">
                <span class="official-value">${money(row.running_average, 4)}</span>
                ${row.latest_date
                    ? `<span class="official-window">última ${shortDate(row.latest_date)}
                        · ${money(row.latest_price, 4)}</span>`
                    : ''}
            </td>
            <td class="num ${changeClass(row.change_percent)}">${percent(row.change_percent)}</td>
            ${rateCell(row.export_rate, row.rate_basis)}
            ${rateCell(row.internal_rate, row.rate_basis)}
            ${daysCell(row)}
            <td>${confidenceTag(row)}</td>`;
        return tr;
    }

    /**
     * The detail of one mineral: the days that built the average, and the scale
     * that turned it into a rate. Both answer the same question — "¿de dónde
     * sale este número?" — which is the first thing anyone asks of an estimate.
     */
    async function detailFor(row, holder) {
        const period = state.estimate;
        const rules = await rulesByMineral();
        const rule = rules[row.mineral_id];

        let series = state.series[row.mineral_id];
        if (!series) {
            series = await market.series(row.mineral_id, {
                date_from: period.period_start, date_to: period.as_of
            });
            state.series[row.mineral_id] = series;
        }

        const prices = series.items.map((item) => item.price);
        const cells = series.items.map((item) => `
            <tr>
                <td>${item.date}</td>
                <td class="num">${money(item.price, 4)}</td>
                <td>${SOURCE_LABELS[item.source] || item.source}</td>
            </tr>`).join('');

        const formula = rule
            ? `regalía = ${money(rule.slope, 5)} × cotización ${
                rule.intercept < 0 ? '−' : '+'} ${money(Math.abs(rule.intercept), 5)},
               acotada entre ${money(rule.min_rate, 2)} % y ${money(rule.max_rate, 2)} %;
               venta interna = ${money(rule.internal_factor * 100, 0)} % de la de exportación`
            : 'sin escala cargada para este mineral';

        holder.innerHTML = `
            <div class="history-box estimate-detail">
                <div class="detail-spark">
                    ${sparkline(prices, [])}
                    <span class="control-hint">
                        ${series.items.length} día${series.items.length === 1 ? '' : 's'}
                        cotizado${series.items.length === 1 ? '' : 's'} del
                        ${shortDate(period.period_start)} al ${shortDate(period.as_of)}
                    </span>
                </div>
                <div class="table-scroll history-table-holder">
                    <table class="data-table history-table">
                        <thead>
                            <tr><th>Fecha</th><th class="num">Precio</th><th>Fuente</th></tr>
                        </thead>
                        <tbody>${cells}</tbody>
                    </table>
                </div>
                <p class="control-hint rule-formula">
                    <strong>Art. 227 de la Ley 535:</strong> ${formula}.
                    ${rule ? `<span class="legal">${escapeHtml(rule.legal_basis)}</span>` : ''}
                </p>
            </div>`;
    }

    function wireToggle(tr, row, body) {
        const detail = document.createElement('tr');
        detail.className = 'history-row';
        detail.hidden = true;
        detail.innerHTML = '<td colspan="8"><span class="control-hint">Cargando…</span></td>';
        body.appendChild(detail);

        tr.querySelector('.verify-toggle').addEventListener('click', async (event) => {
            const button = event.currentTarget;
            const open = button.getAttribute('aria-expanded') === 'true';
            button.setAttribute('aria-expanded', String(!open));
            button.querySelector('.caret').textContent = open ? '▸' : '▾';
            detail.hidden = open;
            if (!open && !detail.dataset.loaded) {
                try {
                    await detailFor(row, detail.querySelector('td'));
                    detail.dataset.loaded = '1';
                } catch (error) {
                    detail.querySelector('td').innerHTML =
                        `<span class="control-hint">${escapeHtml(
                            errorText(error, 'No se pudo leer la serie diaria.'))}</span>`;
                }
            }
        });
    }

    function render(data) {
        state.estimate = data;
        state.series = {};
        const body = qs('#estimateTable tbody');
        body.innerHTML = '';
        data.rows.forEach((row) => {
            const tr = estimateRow(row);
            body.appendChild(tr);
            if (row.source) wireToggle(tr, row, body);
        });

        const quoted = data.rows.filter((row) => row.source).length;
        qs('#estimateMeta').textContent =
            `${quoted} de ${data.rows.length} minerales con fuente diaria · ` +
            `quincena del ${shortDate(data.period_start)} al ${shortDate(data.period_end)}`;
        qs('#estimateNote').textContent =
            `Lo que promedie esta quincena regirá del ${data.valid_from} al ${data.valid_to}. ` +
            `Datos al ${data.as_of}.`;
        qs('#estimatePanel').hidden = qs('#scopeSelect').value === 'RATE';
    }

    async function load() {
        const asOf = qs('#estimateDate').value;
        try {
            render(await market.estimate(asOf || null));
        } catch (error) {
            qs('#estimateMeta').textContent = '';
            qs('#estimateNote').textContent =
                errorText(error, 'No se pudo calcular la cotización anticipada.');
            qs('#estimatePanel').hidden = qs('#scopeSelect').value === 'RATE';
        }
    }

    async function sync() {
        const done = setButtonBusy(qs('#syncButton'), 'Leyendo fuentes…');
        try {
            const result = await market.sync();
            const failed = result.failed_sources || [];
            const detail = `${result.stored} día(s) nuevo(s), ` +
                `${result.already_present} ya estaban`;
            if (failed.length) {
                toast(`${detail}. No respondieron: ${
                    failed.map((code) => SOURCE_LABELS[code] || code).join(', ')}.`, 'error');
            } else {
                toast(`Mercado actualizado: ${detail}.`, 'success');
            }
            await load();
        } catch (error) {
            toast(errorText(error, 'No se pudo leer las fuentes.'), 'error');
        } finally {
            done();
        }
    }

    if (SYNC_ROLES.includes(window.SD_AUTH.getRole())) {
        const button = qs('#syncButton');
        button.hidden = false;
        button.addEventListener('click', sync);
    }

    qs('#estimateDate').addEventListener('change', load);
    qs('#scopeSelect').addEventListener('change', () => {
        qs('#estimatePanel').hidden = qs('#scopeSelect').value === 'RATE';
    });

    load();
});
