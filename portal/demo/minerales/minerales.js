'use strict';

/**
 * Cotizaciones y proyecciones — module logic.
 *
 * Two services answer here: MINING_ANALYSIS projects the minerals and QUOTES
 * projects the dollar. They are deliberately independent — the user may ask for
 * one, the other, or both — and only the sale scenario needs them together,
 * because that is the only question where both movements net out.
 *
 * Every code the services return is translated to wording here. The backend
 * returns data and codes; the sentences belong to the frontend.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.requireAuth()) return;

    const { qs, toast, setButtonBusy } = window.SD_UI;

    qs('#userChip').textContent = window.SD_AUTH.getEmail() || 'usuario';
    qs('#logoutButton').addEventListener('click', () => window.SD_AUTH.logout());
    if (window.SD_SESSION) window.SD_SESSION.mountChip('sessionChip', false);

    const MINING_URL = window.SD_CONFIG.MINING_URL;
    const QUOTES_URL = window.SD_CONFIG.QUOTES_URL;

    // Confidence and method travel as codes; the wording is ours.
    const CONFIDENCE_LABELS = {
        HIGH: 'Alta', MEDIUM: 'Media', LOW: 'Baja',
        INSUFFICIENT: 'Datos insuficientes'
    };
    const METHOD_LABELS = {
        DAMPED_TREND: 'Tendencia amortiguada',
        LINEAR: 'Tendencia lineal',
        MOVING_AVERAGE: 'Promedio móvil',
        NAIVE: 'Sin cambio'
    };

    /**
     * How far the model has actually missed, next to the same measurement for
     * the benchmark it has to beat. Both come from replaying the stored series,
     * so the figure is measured and not an assumed interval — and showing the
     * benchmark is what lets a reader judge whether the projection earns its
     * place instead of taking the margin on faith.
     */
    function accuracyNote(method, error, baselineError) {
        const name = METHOD_LABELS[method] || method;
        if (error === null || error === undefined) {
            return `${name} · sin historia suficiente para medir el error`;
        }
        const versus = (baselineError === null || baselineError === undefined)
            ? ''
            : ` · sin cambio erraría ±${money(baselineError)}`;
        return `${name} · error medido ±${money(error)}${versus}`;
    }
    const SERVICE_ERRORS = {
        NO_RATE_PUBLISHED: 'Todavía no hay cotizaciones del dólar guardadas.',
        SOURCE_UNAVAILABLE: 'El Banco Central no respondió.',
        SOURCE_UNREADABLE: 'La página del Banco Central cambió de forma y no se ' +
            'puede leer con seguridad.',
        INVALID_DATE_RANGE: 'El plazo pedido está fuera de rango.',
        EMPTY_PERIOD: 'No hay datos en ese período.'
    };

    function errorText(error, fallback) {
        return SERVICE_ERRORS[error && error.code] || (error && error.message) || fallback;
    }

    const state = { minerals: null, rate: null, days: 30 };

    // --- formatting -------------------------------------------------------

    /**
     * Two decimals everywhere, matching the published bulletin. The service
     * already rounds the official price HALF_UP, so this only pads and groups —
     * it never re-rounds, which is where a browser and Python disagree.
     */
    function money(value, digits = 2) {
        if (value === null || value === undefined) return '—';
        return Number(value).toLocaleString('es-BO', {
            minimumFractionDigits: digits, maximumFractionDigits: digits
        });
    }

    function percent(value) {
        if (value === null || value === undefined) return '—';
        const sign = value > 0 ? '+' : '';
        return `${sign}${Number(value).toFixed(2)}%`;
    }

    function changeClass(value) {
        if (value === null || value === undefined) return '';
        if (value > 0) return 'up';
        return value < 0 ? 'down' : '';
    }

    /**
     * Draws a sparkline as inline SVG. No chart library: the shape of a series
     * is a line between points, and pulling a dependency for that would be the
     * heaviest thing on the page.
     */
    function sparkline(observed, projected, width = 220, height = 44) {
        const all = observed.concat(projected);
        if (all.length < 2) return '';
        const min = Math.min(...all);
        const max = Math.max(...all);
        const span = (max - min) || 1;
        const step = width / (all.length - 1);
        const point = (value, index) => {
            const x = (index * step).toFixed(1);
            const y = (height - ((value - min) / span) * height).toFixed(1);
            return `${x},${y}`;
        };
        const observedPath = observed.map(point).join(' ');
        // The projection starts at the last observed point so the two lines meet.
        const projectedPath = projected
            .map((value, index) => point(value, observed.length - 1 + index + 1));
        const joined = observed.length
            ? [point(observed[observed.length - 1], observed.length - 1)]
                .concat(projectedPath).join(' ')
            : projectedPath.join(' ');

        return `<svg class="spark" viewBox="0 0 ${width} ${height}"
                     preserveAspectRatio="none" aria-hidden="true">
            <polyline class="spark-observed" points="${observedPath}"></polyline>
            <polyline class="spark-projected" points="${joined}"></polyline>
        </svg>`;
    }

    // --- minerals ---------------------------------------------------------

    async function loadMinerals(days) {
        const data = await window.SD_API.get(
            `${MINING_URL}/v1/mining-analysis/forecast/prices`, { days_ahead: days }
        );
        state.minerals = data;
        renderMinerals(data);
        fillMineralSelect(data);
    }

    /**
     * Renders one official quotation: the figure, the fortnight it averages and
     * the fortnight it rules over. Both windows are shown because a reader who
     * only sees the number takes it for today's price.
     */
    function officialCell(quotation, sameAs) {
        if (!quotation) {
            return `<td class="num muted-cell">${
                sameAs ? 'igual que la próxima' : '—'
            }</td>`;
        }
        const partial = quotation.is_complete === false ? ' parcial' : '';
        const composition = quotation.projected_days > 0
            ? `${quotation.observed_days} días reales + ${quotation.projected_days} proyectados`
            : `${quotation.sample_size} días`;
        return `<td class="num">
            <span class="official-value">${money(quotation.avg_price_low)}</span>
            <span class="official-window">
                rige ${shortDate(quotation.valid_from)}–${shortDate(quotation.valid_to)}
            </span>
            <span class="official-window">
                promedio ${shortDate(quotation.period_start)}–${shortDate(quotation.period_end)}
                · ${composition}${partial}
            </span>
        </td>`;
    }

    function shortDate(value) {
        if (!value) return '—';
        const [, month, day] = value.split('-');
        return `${day}/${month}`;
    }


    /**
     * Every fortnight of one mineral in one table: the ones already published,
     * the one in force, and every projected one the horizon reaches.
     *
     * The projected chain is what makes the plazo selector visible. The
     * headline column only shows the next official price, which is always the
     * fortnight in course, so at 15, 30 or 60 days it looked frozen — the chain
     * is where the horizon actually shows up.
     */
    function periodsRow(item) {
        const rows = [];

        (item.official_history || []).slice().reverse().forEach((entry) => {
            rows.push(periodLine(entry, 'Publicada', 'past'));
        });
        if (item.official_current) {
            rows.push(periodLine(item.official_current, 'Vigente', 'current'));
        }
        (item.official_forecast || []).forEach((entry) => {
            const label = entry.is_complete === false ? 'Proyectada · parcial' : 'Proyectada';
            rows.push(periodLine(entry, label, 'future'));
        });

        const holder = document.createElement('tr');
        holder.className = 'history-row';
        holder.hidden = true;
        holder.innerHTML = `
            <td colspan="8">
                <div class="history-box">
                    <h4>Quincenas de ${item.mineral}</h4>
                    <table class="data-table history-table">
                        <thead>
                            <tr>
                                <th>Estado</th>
                                <th>Promedio de</th>
                                <th class="num">Oficial</th>
                                <th class="num">Registros</th>
                                <th>Rige</th>
                            </tr>
                        </thead>
                        <tbody>${rows.join('')}</tbody>
                    </table>
                    <p class="history-note">
                        Cada cifra es el promedio de los registros de esa quincena
                        para este mineral, y rige la quincena siguiente. En las
                        proyectadas, los días ya cotizados se usan tal cual y sólo
                        se proyecta el resto.
                    </p>
                </div>
            </td>`;
        return holder;
    }

    function periodLine(entry, label, kind) {
        const composition = entry.projected_days > 0
            ? `${entry.observed_days} + ${entry.projected_days} proy.`
            : `${entry.sample_size}`;
        return `
            <tr class="period-${kind}">
                <td><span class="state state-${kind}">${label}</span></td>
                <td>${shortDate(entry.period_start)} – ${shortDate(entry.period_end)}</td>
                <td class="num">${money(entry.avg_price_low)}</td>
                <td class="num">${composition}</td>
                <td>${shortDate(entry.valid_from)} – ${shortDate(entry.valid_to)}</td>
            </tr>`;
    }

    function renderMinerals(data) {
        const body = qs('#mineralsTable tbody');
        body.innerHTML = '';

        data.minerals.forEach((item) => {
            const history = item.history.map((point) => point.price);
            const forecast = item.forecast.map((point) => point.price);
            // The service already reports the last observed quotation; deriving
            // it from the series again would only be a second source of truth.
            const last = item.last_price !== null && item.last_price !== undefined
                ? item.last_price
                : (history.length ? history[history.length - 1] : null);
            const chain = item.official_forecast || [];
            const next = chain[0] || null;
            // The last fortnight the horizon reaches. This is the cell that
            // actually moves when the plazo changes: the next official price is
            // always the fortnight in course, so on its own the selector looked
            // like it did nothing.
            const furthest = chain.length > 1 ? chain[chain.length - 1] : null;

            const row = document.createElement('tr');
            row.className = 'mineral-row';
            const periods = (item.official_history || []).length
                + (item.official_current ? 1 : 0)
                + (item.official_forecast || []).length;
            row.innerHTML = `
                <td>
                    <button class="verify-toggle" type="button"
                            ${periods ? '' : 'disabled'}
                            aria-expanded="false">
                        <span class="caret">▸</span>${item.mineral}</button>
                    ${item.unit ? `<span class="unit">${item.unit}</span>` : ''}
                </td>
                ${officialCell(item.official_current)}
                ${officialCell(next)}
                ${officialCell(furthest, next)}
                <td class="num ${changeClass(item.official_change_percent)}">${
                    percent(item.official_change_percent)
                }</td>
                <td class="num daily">${money(last)}</td>
                <td><span class="tag tag-${item.confidence}">${
                    CONFIDENCE_LABELS[item.confidence] || item.confidence
                }</span><span class="method">${accuracyNote(
                    item.method, item.mean_absolute_error, item.baseline_error
                )}</span></td>
                <td class="spark-cell">${sparkline(history, forecast)}</td>`;
            body.appendChild(row);

            if (periods) {
                body.appendChild(periodsRow(item));
                row.querySelector('.verify-toggle').addEventListener('click', (event) => {
                    const button = event.currentTarget;
                    const open = button.getAttribute('aria-expanded') === 'true';
                    button.setAttribute('aria-expanded', String(!open));
                    button.querySelector('.caret').textContent = open ? '▸' : '▾';
                    row.nextElementSibling.hidden = open;
                });
            }
        });

        qs('#horizonHead').textContent = `Al final de ${data.days_ahead} días`;

        const current = data.minerals.find((item) => item.official_current);
        const inForce = current
            ? ` · oficial vigente del ${current.official_current.valid_from}` +
              ` al ${current.official_current.valid_to}`
            : '';
        const reach = Math.max(
            ...data.minerals.map((item) => (item.official_forecast || []).length), 0
        );
        const reachText = reach
            ? ` · el plazo alcanza ${reach} quincena${reach === 1 ? '' : 's'}`
            : '';
        qs('#mineralsMeta').textContent =
            `${data.minerals.length} minerales${inForce}${reachText}`;
        qs('#mineralsPanel').hidden = false;
    }

    function fillMineralSelect(data) {
        const select = qs('#mineralSelect');
        const previous = select.value;
        select.innerHTML = '';
        data.minerals.forEach((item) => {
            const option = document.createElement('option');
            option.value = item.mineral;
            option.textContent = item.mineral;
            select.appendChild(option);
        });
        if (previous) select.value = previous;
        syncScenarioInputs();
    }

    // --- exchange rate ----------------------------------------------------

    async function loadRate(days) {
        const data = await window.SD_API.get(
            `${QUOTES_URL}/v1/quotes/exchange-rates/forecast`, { days_ahead: days }
        );
        state.rate = data;
        renderRate(data);
    }


    const WEEKDAYS = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves',
                      'viernes', 'sábado'];

    /**
     * Reads an ISO date as a local calendar date. `new Date('2026-09-03')`
     * parses as UTC and, west of Greenwich, renders as the day before — which
     * would put every quotation on the wrong weekday.
     */
    function asLocalDate(iso) {
        const [year, month, day] = iso.split('-').map(Number);
        return new Date(year, month - 1, day);
    }

    function weekdayOf(iso) {
        return WEEKDAYS[asLocalDate(iso).getDay()];
    }

    /**
     * The rate series as numbers, newest first, with the day-to-day move and
     * the accumulated one. A chart shows the shape; the settlement figure is
     * read off a table, and the drop between two dates is the number a seller
     * argues with.
     */
    function renderRateTable(data) {
        const body = qs('#rateTable tbody');
        const withProjection = qs('#rateShowProjected').checked;

        const observed = data.history.map((point) => ({
            date: point.date, rate: point.rate, projected: false
        }));
        const projected = withProjection
            ? data.projected.map((point) => ({
                date: point.date, rate: point.rate, projected: true
            }))
            : [];
        const series = observed.concat(projected);
        if (!series.length) {
            body.innerHTML = '';
            return;
        }

        const base = series[0].rate;
        const rows = series.map((entry, index) => {
            const previous = index > 0 ? series[index - 1].rate : null;
            const step = previous ? ((entry.rate - previous) / previous) * 100 : null;
            const total = base ? ((entry.rate - base) / base) * 100 : null;
            const state = entry.projected
                ? '<span class="state state-future">Proyectada</span>'
                : '<span class="state state-past">Publicada</span>';
            return `
                <tr class="${entry.projected ? 'period-future' : ''}">
                    <td>${entry.date}</td>
                    <td>${weekdayOf(entry.date)}</td>
                    <td class="num">${money(entry.rate)}</td>
                    <td class="num ${changeClass(step)}">${percent(step)}</td>
                    <td class="num ${changeClass(total)}">${percent(total)}</td>
                    <td>${state}</td>
                </tr>`;
        });

        // Newest first: the current rate is what a reader looks for.
        body.innerHTML = rows.reverse().join('');
    }

    function renderRate(data) {
        const projectedLabel = data.final_rate === null
            ? 'Sin proyección'
            : `${money(data.final_rate)} Bs`;

        qs('#rateFigures').innerHTML = `
            <div class="figure">
                <span class="figure-label">${
                    data.valid_from && data.valid_to && data.valid_from !== data.valid_to
                        ? `Vigente ${shortDate(data.valid_from)} – ${shortDate(data.valid_to)}`
                        : `Vigente hoy (${shortDate(data.last_date)})`
                }</span>
                <span class="figure-value">${money(data.last_rate)} Bs</span>
                ${data.valid_from !== data.valid_to ? `<span class="figure-note">
                    El BCB publica el viernes la cotización del fin de semana:
                    rige hasta el lunes inclusive.
                </span>` : ''}
            </div>
            <div class="figure">
                <span class="figure-label">En ${data.days_ahead} días</span>
                <span class="figure-value">${projectedLabel}</span>
            </div>
            <div class="figure">
                <span class="figure-label">Cambio</span>
                <span class="figure-value ${changeClass(data.change_percent)}">${
                    percent(data.change_percent)
                }</span>
            </div>
            <div class="figure">
                <span class="figure-label">Confianza</span>
                <span class="figure-value"><span class="tag tag-${data.confidence}">${
                    CONFIDENCE_LABELS[data.confidence] || data.confidence
                }</span></span>
            </div>
            <div class="figure figure-wide">
                <span class="figure-label">Modelo</span>
                <span class="figure-note">${
                    data.accuracy
                        ? accuracyNote(data.accuracy.method,
                                       data.accuracy.mean_absolute_error,
                                       data.accuracy.baseline_error) +
                          ` · sobre ${data.accuracy.windows} réplicas`
                        : '—'
                }</span>
            </div>`;

        qs('#rateChart').innerHTML = sparkline(
            data.history.map((point) => point.rate),
            data.projected.map((point) => point.rate),
            640, 140
        );
        qs('#rateMeta').textContent =
            `${data.history.length} días observados desde ${data.history[0].date}`;
        renderRateTable(data);
        qs('#ratePanel').hidden = false;
    }

    // --- sale scenario ----------------------------------------------------

    function selectedMineral() {
        if (!state.minerals) return null;
        const name = qs('#mineralSelect').value;
        return state.minerals.minerals.find((item) => item.mineral === name) || null;
    }

    /**
     * Prefills the unit price with the mineral's own last quotation, so the
     * comparison starts from a real number instead of one the user invents.
     */
    /**
     * Prefills the unit price with the mineral's **official** quotation, which
     * is the figure a sale is actually settled at. Using the last daily quote
     * would start the comparison from a number nobody liquidates against.
     */
    function syncScenarioInputs() {
        const mineral = selectedMineral();
        const hint = qs('#scenarioHint');
        if (!mineral) {
            hint.textContent = '';
            return;
        }
        const official = mineral.official_current;
        if (official && !qs('#priceInput').dataset.touched) {
            qs('#priceInput').value = official.avg_price_low;
        }
        if (!official) {
            hint.textContent = `Todavía no hay cotización oficial de ${mineral.mineral}.`;
            return;
        }
        hint.textContent = mineral.official_change_percent === null
            ? `Precio oficial de ${mineral.mineral} vigente del ` +
              `${official.valid_from} al ${official.valid_to}. Sin proyección ` +
              'de la próxima quincena: se comparará solo el movimiento del dólar.'
            : `Precio oficial de ${mineral.mineral} (promedio del ` +
              `${official.period_start} al ${official.period_end}), vigente del ` +
              `${official.valid_from} al ${official.valid_to}. Se aplicará el ` +
              `cambio hacia la próxima oficial (${percent(mineral.official_change_percent)}).`;
    }

    async function runScenario() {
        const mineral = selectedMineral();
        const body = {
            quantity: Number(qs('#quantityInput').value),
            unit_price_usd: Number(qs('#priceInput').value),
            days_ahead: state.days
        };
        // The miner settles at the official price, so the movement that matters
        // is the one between fortnightly averages, not between daily quotes.
        if (mineral && mineral.official_change_percent !== null
            && mineral.official_change_percent !== undefined) {
            body.mineral_change_percent = mineral.official_change_percent;
        }
        if (!(body.quantity > 0) || !(body.unit_price_usd > 0)) {
            toast('La cantidad y el precio deben ser mayores que cero.', 'error');
            return;
        }

        const data = await window.SD_API.post(
            `${QUOTES_URL}/v1/quotes/sale-scenario`, body
        );
        renderScenario(data, mineral);
    }

    function renderScenario(data, mineral) {
        const name = mineral ? mineral.mineral : 'el mineral';
        if (!data.projected) {
            qs('#scenarioResult').innerHTML = `
                <p class="scenario-verdict">
                    No hay historia suficiente del dólar para proyectar, así que
                    solo se puede valorizar la venta de hoy:
                    <strong>${money(data.today.amount_bob, 2)} Bs</strong>.
                </p>`;
            return;
        }

        const better = data.difference_bob > 0;
        const verdict = better
            ? `Esperar ${data.days_ahead} días rinde ${money(Math.abs(data.difference_bob), 2)} Bs más`
            : `Esperar ${data.days_ahead} días cuesta ${money(Math.abs(data.difference_bob), 2)} Bs`;

        qs('#scenarioResult').innerHTML = `
            <div class="table-scroll">
                <table class="data-table scenario-table">
                    <thead>
                        <tr>
                            <th></th>
                            <th class="num">Tipo de cambio</th>
                            <th class="num">Precio de ${name}</th>
                            <th class="num">USD</th>
                            <th class="num">Bolivianos</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Vender hoy</td>
                            <td class="num">${money(data.today.exchange_rate)}</td>
                            <td class="num">${money(data.today.mineral_price)}</td>
                            <td class="num">${money(data.today.amount_usd, 2)}</td>
                            <td class="num">${money(data.today.amount_bob, 2)}</td>
                        </tr>
                        <tr>
                            <td>En ${data.days_ahead} días</td>
                            <td class="num">${money(data.projected.exchange_rate)}</td>
                            <td class="num">${money(data.projected.mineral_price)}</td>
                            <td class="num">${money(data.projected.amount_usd, 2)}</td>
                            <td class="num">${money(data.projected.amount_bob, 2)}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
            <p class="scenario-verdict ${better ? 'up' : 'down'}">
                ${verdict} (${percent(data.difference_percent)}).
                <span class="scenario-note">
                    Dólar ${percent(data.rate_change_percent)} ·
                    ${name} ${percent(data.mineral_change_percent)} ·
                    confianza ${CONFIDENCE_LABELS[data.rate_confidence] || data.rate_confidence}
                </span>
            </p>`;
    }

    // --- orchestration ----------------------------------------------------

    async function run() {
        const scope = qs('#scopeSelect').value;
        const days = Number(qs('#daysInput').value);
        if (!(days >= 1 && days <= 90)) {
            toast('El plazo debe estar entre 1 y 90 días.', 'error');
            return;
        }
        state.days = days;

        const done = setButtonBusy(qs('#runButton'), 'Proyectando…');
        qs('#errorState').hidden = true;
        try {
            const jobs = [];
            if (scope !== 'RATE') jobs.push(loadMinerals(days));
            if (scope !== 'MINERALS') jobs.push(loadRate(days));
            await Promise.all(jobs);

            qs('#mineralsPanel').hidden = scope === 'RATE';
            qs('#ratePanel').hidden = scope === 'MINERALS';
            // The scenario nets both movements, so it only makes sense together.
            qs('#scenarioPanel').hidden = scope !== 'BOTH';
        } catch (error) {
            qs('#errorText').textContent = errorText(error, 'No se pudo consultar el servicio.');
            qs('#errorState').hidden = false;
        } finally {
            done();
        }
    }

    qs('#rateToggle').addEventListener('click', (event) => {
        const holder = qs('#rateTableHolder');
        holder.hidden = !holder.hidden;
        event.currentTarget.setAttribute('aria-expanded', String(!holder.hidden));
        event.currentTarget.textContent = holder.hidden ? 'Ver la tabla' : 'Ocultar la tabla';
    });
    qs('#rateShowProjected').addEventListener('change', () => {
        if (state.rate) renderRateTable(state.rate);
    });

    qs('#runButton').addEventListener('click', run);
    qs('#scopeSelect').addEventListener('change', run);
    qs('#mineralSelect').addEventListener('change', syncScenarioInputs);
    qs('#priceInput').addEventListener('input', (event) => {
        event.target.dataset.touched = '1';
    });
    qs('#scenarioButton').addEventListener('click', async () => {
        const done = setButtonBusy(qs('#scenarioButton'), 'Comparando…');
        try {
            await runScenario();
        } catch (error) {
            toast(errorText(error, 'No se pudo comparar el escenario.'), 'error');
        } finally {
            done();
        }
    });

    // The interpretation layer reads what each view is showing, as data.
    window.SD_AI.registerView('minerals_forecast', () => state.minerals);
    window.SD_AI.registerView('rate_forecast', () => state.rate);
    window.SD_AI.registerView('sale_scenario', () => ({
        minerals: state.minerals, rate: state.rate, days_ahead: state.days
    }));
    window.SD_AI.mountExplain('mineralsAi', 'minerals_forecast');
    window.SD_AI.mountExplain('rateAi', 'rate_forecast');
    window.SD_AI.mountExplain('scenarioAi', 'sale_scenario');

    run();
});
