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

    const { qs, qsAll, toast, setButtonBusy } = window.SD_UI;

    qs('#userChip').textContent = window.SD_AUTH.getEmail() || 'usuario';
    qs('#logoutButton').addEventListener('click', () => window.SD_AUTH.logout());
    if (window.SD_SESSION) window.SD_SESSION.mountChip('sessionChip', false);

    const QUOTES_URL = window.SD_CONFIG.QUOTES_URL;

    // Formatters, code wording and the sparkline live in `minerales_shared.js`,
    // shared with the anticipated-quotation panel: the same figure has to read
    // the same way on both.
    const {
        MINING_BASE, CONFIDENCE_LABELS, METHOD_LABELS, errorText,
        money, percent, changeClass, shortDate, sparkline
    } = window.SD_MIN;

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
    // `modelPicked` distingue el modelo que eligió el usuario del que elegimos
    // por él. Mientras no elija, el que manda es el de menor error medido, que
    // puede cambiar al cambiar el plazo; en cuanto elige, su elección se
    // respeta y no se la sobrescribe a la espalda.
    const state = { minerals: null, bench: null, model: null,
                    modelPicked: false, scenario: null, days: 30, ratePage: 0 };

    // Ten rows per page, like every table of the product: a scrolling box of
    // eighty quotations was a wall, and the reader lost the header.
    const RATE_ROWS_PER_PAGE = 10;

    // --- formatting -------------------------------------------------------

    // --- minerals ---------------------------------------------------------

    async function loadMinerals(days) {
        const data = await window.SD_API.get(
            `${MINING_BASE}/forecast/prices`,
            { days_ahead: days, method: qs('#mineralModel').value }
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

    /**
     * Con año: el arranque de la serie es una fecha histórica y sin el año no
     * se entiende de qué régimen se está hablando.
     */
    function fullDate(value) {
        if (!value) return '—';
        const [year, month, day] = value.split('-');
        return `${day}/${month}/${year}`;
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
        state.scenario = data;
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
            // Un solo llamado: el banco de modelos ya trae el histórico, el
            // vigente y la confianza, así que /forecast sobraba acá.
            if (scope !== 'MINERALS') jobs.push(loadBench(days));
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

    qs('#runButton').addEventListener('click', run);
    qs('#scopeSelect').addEventListener('change', run);
    qs('#mineralModel').addEventListener('change', run);
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

    /**
     * Lo que la vista del dólar está mostrando: la respuesta del servicio tal
     * cual, más el único dato que la respuesta no puede traer — cuál de los
     * modelos está eligiendo el usuario. Sin eso la explicación hablaba de
     * nueve proyecciones cuando en pantalla se ve una.
     */
    function ratePayload() {
        if (!state.bench) return null;
        return Object.assign({}, state.bench, { selected_model: state.model });
    }

    // The interpretation layer reads what each view is showing, as data.
    window.SD_AI.registerView('minerals_forecast', () => state.minerals);
    window.SD_AI.registerView('rate_forecast', ratePayload);
    window.SD_AI.registerView('sale_scenario', () => ({
        minerals: state.minerals, rate: ratePayload(),
        scenario: state.scenario, days_ahead: state.days
    }));
    window.SD_AI.mountExplain('mineralsAi', 'minerals_forecast',
                             qs('#mineralsPanel').querySelector('.panel-head'));
    window.SD_AI.mountExplain('rateAi', 'rate_forecast',
                             qs('#ratePanel').querySelector('.panel-head'));
    window.SD_AI.mountExplain('scenarioAi', 'sale_scenario',
                             qs('#scenarioPanel').querySelector('.panel-head'));

    run();
});
