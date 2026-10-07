'use strict';

/**
 * Factores externos y tipo de cambio — the dollar.
 *
 * The official rate (BCB) with its projection and the bench of models, moved
 * here from the minerals page: the exchange rate belongs to the commercial
 * side and minerals is a different product (Rafael, 05-oct). Next to it, the
 * parallel dollar: the USDT of the Binance P2P market, read once a day.
 *
 * Every code the service returns is translated to wording here.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.requireAuth()) return;

    const { qs, toast, setButtonBusy } = window.SD_UI;

    qs('#userChip').textContent = window.SD_AUTH.getEmail() || 'usuario';
    qs('#logoutButton').addEventListener('click', () => window.SD_AUTH.logout());
    if (window.SD_SESSION) window.SD_SESSION.mountChip('sessionChip', false);

    const QUOTES_URL = window.SD_CONFIG.QUOTES_URL;
    const {
        CONFIDENCE_LABELS, METHOD_LABELS, errorText,
        money, percent, changeClass, shortDate, fullDate, sparkline
    } = window.SD_MIN;

    // `modelPicked` distingue el modelo que eligió el usuario del que elegimos
    // por él: mientras no elija, manda el de menor error medido.
    const state = { bench: null, model: null, modelPicked: false, ratePage: 0,
                    parallel: [], parallelPage: 0 };

    // Ten rows per page, like every table of the product.
    const RATE_ROWS_PER_PAGE = 10;

    // --- exchange rate ----------------------------------------------------

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
    function renderRateTable(data, run) {
        const body = qs('#rateTable tbody');
        const withProjection = qs('#rateShowProjected').checked;

        const observed = data.history.map((point) => ({
            date: point.date, rate: point.rate, projected: false
        }));
        // Lo proyectado sale del modelo elegido, no de un método fijo: es la
        // misma serie que dibuja el gráfico de arriba.
        const projected = (withProjection && run)
            ? run.projected.map((point) => ({
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
            const status = entry.projected
                ? '<span class="state state-future">Proyectada</span>'
                : '<span class="state state-past">Publicada</span>';
            return `
                <tr class="${entry.projected ? 'period-future' : ''}">
                    <td>${entry.date}</td>
                    <td>${weekdayOf(entry.date)}</td>
                    <td class="num">${money(entry.rate)}</td>
                    <td class="num ${changeClass(step)}">${percent(step)}</td>
                    <td class="num ${changeClass(total)}">${percent(total)}</td>
                    <td>${status}</td>
                </tr>`;
        });

        // Newest first: the current rate is what a reader looks for.
        const ordered = rows.reverse();
        const pages = Math.max(1, Math.ceil(ordered.length / RATE_ROWS_PER_PAGE));
        state.ratePage = Math.min(Math.max(state.ratePage, 0), pages - 1);
        const from = state.ratePage * RATE_ROWS_PER_PAGE;
        body.innerHTML = ordered.slice(from, from + RATE_ROWS_PER_PAGE).join('');

        qs('#rateCount').textContent = `${ordered.length} cotizaciones`;
        qs('#ratePage').textContent = `${state.ratePage + 1} / ${pages}`;
        qs('#ratePrev').disabled = state.ratePage === 0;
        qs('#rateNext').disabled = state.ratePage >= pages - 1;
        qs('#ratePager').hidden = ordered.length <= RATE_ROWS_PER_PAGE;
    }

    /**
     * Cuánto histórico sostiene a los modelos, en los dos números que no se
     * deducen uno del otro: cotizaciones publicadas y días de calendario que
     * cubren. El BCB publica en días hábiles y el viernes cubre el fin de
     * semana, así que 60 cotizaciones no son 60 días ni al revés.
     */
    function seriesSpan(data) {
        const history = data.history || [];
        if (!history.length) return null;
        const first = history[0].date;
        const last = history[history.length - 1].date;
        const days = Math.round(
            (asLocalDate(last) - asLocalDate(first)) / 86400000
        ) + 1;
        return { start: first, end: last, observations: history.length, days: days };
    }

    function renderSeriesNotes(data) {
        const span = seriesSpan(data);
        if (!span) {
            qs('#rateMeta').textContent = '';
            qs('#rateSeriesNote').textContent = '';
            return;
        }
        qs('#rateMeta').textContent =
            `${span.observations} cotizaciones publicadas · `
            + `${span.days} días desde el ${fullDate(span.start)}`;
        qs('#rateSeriesNote').textContent =
            `Los modelos se ajustan sobre ${span.observations} cotizaciones `
            + `oficiales, que cubren ${span.days} días corridos desde el `
            + `${fullDate(span.start)}, cuando el tipo de cambio dejó de estar `
            + 'fijo. Los años previos pertenecen a otro régimen y no son '
            + 'comparables con lo que vino después.';
    }

    // --- modelos de proyección -------------------------------------------

    const MODEL_LABELS = {
        NAIVE: 'Sin cambio (referencia)',
        MEAN: 'Promedio histórico',
        DRIFT: 'Deriva',
        LINEAR: 'Tendencia lineal',
        MOVING_AVERAGE: 'Promedio móvil',
        SIMPLE_EXPONENTIAL: 'Suavizado exponencial simple',
        HOLT: 'Holt con tendencia',
        DAMPED_TREND: 'Tendencia amortiguada',
        THETA: 'Método Theta'
    };

    const MODEL_HINTS = {
        NAIVE: 'Repite la última cotización. Es el rival a vencer: en tipos de '
             + 'cambio casi nada le gana de forma sostenida a horizontes cortos.',
        MEAN: 'Repite el promedio de toda la serie. Sirve de contraste: si gana, '
            + 'la serie no tiene tendencia.',
        DRIFT: 'Extiende la pendiente entre el primer y el último dato.',
        LINEAR: 'Recta de mínimos cuadrados sobre toda la serie. Extrapola la '
              + 'pendiente sin freno.',
        MOVING_AVERAGE: 'Repite el promedio de los últimos días. Sin tendencia.',
        SIMPLE_EXPONENTIAL: 'Nivel que sigue a la serie, cargando el peso en lo '
                          + 'reciente. Sin tendencia.',
        HOLT: 'Nivel más tendencia, sin amortiguar: la pendiente se mantiene.',
        DAMPED_TREND: 'Nivel más tendencia que se desvanece con la distancia, '
                    + 'para que la proyección se asiente en vez de dispararse.',
        THETA: 'Promedia una recta de largo plazo con un suavizado que sigue lo '
             + 'reciente. Fuerte en series cortas.'
    };

    /**
     * El modelo por defecto es el que menos ha errado, medido sobre esta misma
     * serie — no un nombre elegido en el código.
     *
     * El servicio devuelve los modelos ordenados por su error y deja al final
     * los que no pudo medir, así que el primero medido es el más ajustado al
     * plazo pedido. Fijar uno acá era una decisión de negocio escondida en el
     * frontend, y además podía quedar desactualizada: el mejor a 7 días no es
     * necesariamente el mejor a 90.
     */
    function bestModel(data) {
        const measured = data.runs.find(
            (run) => run.mean_absolute_error !== null
                  && run.mean_absolute_error !== undefined
        );
        const chosen = measured || data.runs[0];
        return chosen ? chosen.model : null;
    }

    async function loadBench(days) {
        const data = await window.SD_API.get(
            `${QUOTES_URL}/v1/quotes/exchange-rates/bench`, { days_ahead: days }
        );
        state.bench = data;
        // Mientras el usuario no haya elegido, manda el medido. Si eligió, se
        // respeta salvo que ese modelo ya no venga en la respuesta.
        if (!state.modelPicked
            || !data.runs.some((run) => run.model === state.model)) {
            state.model = bestModel(data);
        }
        fillModelSelect(data);
        renderSeriesNotes(data);
        renderModel();
        renderBenchTable(data);
    }

    function fillModelSelect(data) {
        const select = qs('#rateModel');
        // En el orden en que el servicio los devolvió: del que menos erró al que
        // más, para que la lista misma sea una recomendación.
        select.innerHTML = data.runs.map((run) => {
            const label = MODEL_LABELS[run.model] || run.model;
            const error = run.mean_absolute_error === null
                ? 'sin medir'
                : `±${money(run.mean_absolute_error)}`;
            return `<option value="${run.model}"${
                run.model === state.model ? ' selected' : ''
            }>${label} · ${error}</option>`;
        }).join('');
    }

    function currentRun() {
        if (!state.bench) return null;
        return state.bench.runs.find((run) => run.model === state.model) || null;
    }

    /**
     * La proyección del modelo elegido: gráfico, cifras y la serie día por día.
     *
     * Una sola línea proyectada, no nueve. Superponerlas contestaba una pregunta
     * que nadie hizo y hacía ilegible la que importa — cuánto va a valer el
     * dólar según el modelo que elegí.
     */
    function renderModel() {
        const run = currentRun();
        const data = state.bench;
        if (!run || !data) return;

        qs('#rateModelNote').textContent = MODEL_HINTS[run.model] || '';
        renderDefaultNote(data, run);

        // Cifras de cabecera, ahora del modelo elegido.
        const projectedLabel = run.final_rate === null
            ? 'Sin proyección'
            : `${money(run.final_rate)} Bs`;
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
                <span class="figure-value ${changeClass(run.change_percent)}">${
                    percent(run.change_percent)
                }</span>
            </div>
            <div class="figure">
                <span class="figure-label">Confianza</span>
                <span class="figure-value"><span class="tag tag-${data.confidence}">${
                    CONFIDENCE_LABELS[data.confidence] || data.confidence
                }</span></span>
            </div>
            </div>`;

        qs('#rateChart').innerHTML = sparkline(
            data.history.map((point) => point.rate),
            run.projected.map((point) => point.rate),
            640, 150
        );

        renderRateTable(data, run);
    }

    /**
     * Por qué el modelo que se ve al entrar es ese y no otro.
     *
     * Se dice con el número que lo decidió —su error medido y sobre cuántas
     * réplicas— porque "es el más preciso" sin la cifra es una afirmación que
     * el lector no puede auditar. Cuando el usuario elige otro, la nota deja de
     * justificar y pasa a señalar cuál era el medido, para que la comparación
     * siga estando a la vista.
     */
    function renderDefaultNote(data, run) {
        const best = bestModel(data);
        const holder = qs('#rateDefaultNote');
        const bestRun = data.runs.find((item) => item.model === best);

        if (!bestRun || bestRun.mean_absolute_error === null
            || bestRun.mean_absolute_error === undefined) {
            holder.textContent = 'Todavía no hay historia suficiente para medir '
                + 'el error de los modelos, así que ninguno se puede presentar '
                + 'como el más preciso.';
            return;
        }

        const precision = `±${money(bestRun.mean_absolute_error)} Bs en promedio `
            + `sobre ${data.windows} réplicas de la serie`;

        holder.textContent = run.model === best
            ? `Viene elegido por defecto porque es el que menos ha errado al `
              + `proyectar a ${data.days_ahead} días: ${precision}.`
            : `Estás viendo ${MODEL_LABELS[run.model] || run.model}. El de menor `
              + `error medido a ${data.days_ahead} días es `
              + `${MODEL_LABELS[best] || best} (${precision}), y por eso es el `
              + 'que viene por defecto.';
    }

    /**
     * La comparación entre modelos, plegada.
     *
     * Va aparte y explicada porque el error medido es un promedio sobre toda la
     * historia al horizonte pedido — no dice nada sobre si la cifra de hoy va a
     * acertar. Presentarlo junto a la proyección los hacía parecer lo mismo.
     */
    function renderBenchTable(data) {
        qs('#benchHorizon').textContent = data.days_ahead;
        const body = qs('#benchTable tbody');

        body.innerHTML = data.runs.map((run) => `
            <tr class="${run.model === state.model ? 'model-on' : ''}">
                <td>${MODEL_LABELS[run.model] || run.model}</td>
                <td class="num">${money(run.final_rate)}</td>
                <td class="num ${changeClass(run.change_percent)}">${
                    percent(run.change_percent)
                }</td>
                <td class="num">${
                    run.mean_absolute_error === null
                        ? 'sin medir'
                        : '±' + money(run.mean_absolute_error)
                }</td>
                <td>${
                    run.mean_absolute_error === null
                        ? '<span class="state state-past">Historia insuficiente</span>'
                        : `<span class="state state-${
                            run === data.runs[0] ? 'current' : 'past'
                          }">${run === data.runs[0] ? 'El más preciso' : 'Medido'}</span>`
                }</td>
            </tr>`).join('');
    }


    // --- official against USDT -------------------------------------------

    /**
     * Both series on one scale: drawn on separate scales the gap disappears,
     * and the gap is the point of the chart.
     */
    function pairChart(official, parallel, width = 220, height = 44) {
        const all = official.concat(parallel).filter((value) => value !== null);
        if (all.length < 2) return '';
        const min = Math.min(...all);
        const span = (Math.max(...all) - min) || 1;
        const step = width / Math.max(official.length - 1, 1);
        const line = (values) => values
            .map((value, index) => (value === null ? null
                : `${(index * step).toFixed(1)},${(height - ((value - min) / span) * height).toFixed(1)}`))
            .filter(Boolean).join(' ');
        return `<svg class="spark" viewBox="0 0 ${width} ${height}"
                     preserveAspectRatio="none" aria-hidden="true">
            <polyline class="spark-observed" points="${line(official)}"></polyline>
            <polyline class="spark-parallel" points="${line(parallel)}"></polyline>
        </svg>`;
    }

    /**
     * One row per USDT day, next to the official rate in force that day: the
     * BCB does not publish every day, so a day without its own rate carries
     * the latest one before it.
     */
    function pairRows(official, usdt) {
        const byDay = official.slice().sort((a, b) => a.date.localeCompare(b.date));
        let cursor = 0;
        let inForce = null;
        return usdt.slice().sort((a, b) => a.date.localeCompare(b.date)).map((row) => {
            while (cursor < byDay.length && byDay[cursor].date <= row.date) {
                inForce = byDay[cursor].rate;
                cursor += 1;
            }
            const gap = inForce ? (row.rate / inForce - 1) * 100 : null;
            return { date: row.date, official: inForce, usdt: row.rate, gap };
        });
    }

    function renderParallelFigures(rows) {
        const gaps = rows.map((row) => row.gap).filter((gap) => gap !== null);
        const last = rows[rows.length - 1];
        const widest = rows.reduce((best, row) =>
            (row.gap !== null && (best === null || Math.abs(row.gap) > Math.abs(best.gap)) ? row : best), null);
        const mean = gaps.length ? gaps.reduce((sum, gap) => sum + gap, 0) / gaps.length : null;
        const figure = (label, value, note) => `
            <div class="figure">
                <span class="figure-label">${label}</span>
                <span class="figure-value">${value}</span>
                ${note ? `<span class="figure-note">${note}</span>` : ''}
            </div>`;
        qs('#parallelFigures').innerHTML =
            figure(`USDT (${shortDate(last.date)})`, `${money(last.usdt)} Bs`,
                   `oficial ${last.official ? money(last.official) : '—'} Bs`) +
            figure('Brecha de ese día', last.gap === null ? '—' : percent(last.gap)) +
            figure('Brecha media', mean === null ? '—' : percent(mean),
                   `${gaps.length} días`) +
            figure('Brecha más amplia', widest ? percent(widest.gap) : '—',
                   widest ? fullDate(widest.date) : '');
    }

    function renderParallelTable() {
        const ordered = state.parallel.slice().reverse();
        const pages = Math.max(1, Math.ceil(ordered.length / RATE_ROWS_PER_PAGE));
        state.parallelPage = Math.min(Math.max(state.parallelPage, 0), pages - 1);
        const from = state.parallelPage * RATE_ROWS_PER_PAGE;
        qs('#parallelTable tbody').innerHTML = ordered.slice(from, from + RATE_ROWS_PER_PAGE)
            .map((row) => `<tr><td>${fullDate(row.date)}</td>` +
                `<td class="num">${row.official ? money(row.official) : '—'}</td>` +
                `<td class="num">${money(row.usdt)}</td>` +
                `<td class="num ${changeClass(row.gap)}">${row.gap === null ? '—' : percent(row.gap)}</td></tr>`)
            .join('');
        qs('#parallelCount').textContent = `${ordered.length} días`;
        qs('#parallelPage').textContent = `${state.parallelPage + 1} / ${pages}`;
        qs('#parallelPrev').disabled = state.parallelPage === 0;
        qs('#parallelNext').disabled = state.parallelPage >= pages - 1;
        qs('#parallelPager').hidden = ordered.length <= RATE_ROWS_PER_PAGE;
    }

    /** The whole floating period of both series: the service starts it at 27/06/2026. */
    async function loadParallel() {
        const url = `${QUOTES_URL}/v1/quotes/exchange-rates`;
        const [official, usdt] = await Promise.all([
            window.SD_API.get(url, { currency: 'USD' }),
            window.SD_API.get(url, { currency: 'USDT' })
        ]);
        state.parallel = pairRows(official.rates || [], usdt.rates || []);
        state.parallelPage = 0;
        if (!state.parallel.length) {
            qs('#parallelFigures').innerHTML = '';
            qs('#parallelChart').innerHTML = '';
            qs('#parallelMeta').textContent = '';
            qs('#parallelTable tbody').innerHTML =
                '<tr><td colspan="4">Todavía no hay lecturas del USDT.</td></tr>';
            return;
        }
        const first = state.parallel[0].date;
        qs('#parallelMeta').textContent =
            `${state.parallel.length} días desde el ${fullDate(first)}`;
        renderParallelFigures(state.parallel);
        const officials = state.parallel.map((row) => row.official);
        const usdts = state.parallel.map((row) => row.usdt);
        const values = officials.concat(usdts).filter((value) => value !== null);
        const last = state.parallel[state.parallel.length - 1].date;
        // Without a scale the reader sees a shape, not a figure.
        qs('#parallelChart').innerHTML = `
            <div class="pair-chart">
                <div class="pair-axis">
                    <span>${money(Math.max(...values))}</span>
                    <span>${money(Math.min(...values))}</span>
                </div>
                ${pairChart(officials, usdts)}
            </div>
            <div class="pair-dates"><span>${fullDate(first)}</span><span>${fullDate(last)}</span></div>`;
        renderParallelTable();
    }

    async function run() {
        const days = Number(qs('#daysInput').value);
        if (!(days >= 1 && days <= 90)) {
            toast('El plazo debe estar entre 1 y 90 días.', 'error');
            return;
        }
        const done = setButtonBusy(qs('#runButton'), 'Proyectando…');
        qs('#errorState').hidden = true;
        try {
            await Promise.all([loadBench(days), loadParallel()]);
            qs('#ratePanel').hidden = false;
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
        state.ratePage = 0;
        if (state.bench) renderRateTable(state.bench, currentRun());
    });
    qs('#ratePrev').addEventListener('click', () => {
        state.ratePage -= 1;
        if (state.bench) renderRateTable(state.bench, currentRun());
    });
    qs('#rateNext').addEventListener('click', () => {
        state.ratePage += 1;
        if (state.bench) renderRateTable(state.bench, currentRun());
    });
    qs('#rateModel').addEventListener('change', (event) => {
        state.model = event.target.value;
        state.modelPicked = true;
        renderModel();
        renderBenchTable(state.bench);
    });
    qs('#parallelPrev').addEventListener('click', () => {
        state.parallelPage -= 1;
        renderParallelTable();
    });
    qs('#parallelNext').addEventListener('click', () => {
        state.parallelPage += 1;
        renderParallelTable();
    });
    qs('#runButton').addEventListener('click', run);

    /** What the dollar view shows, plus the model the user is looking at. */
    function ratePayload() {
        if (!state.bench) return null;
        return Object.assign({}, state.bench, { selected_model: state.model });
    }
    window.SD_AI.registerView('rate_forecast', ratePayload);
    window.SD_AI.mountExplain('rateAi', 'rate_forecast',
                             qs('#ratePanel').querySelector('.panel-head'));

    run();
});
