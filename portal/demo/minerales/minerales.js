'use strict';

/**
 * Minerales — module logic.
 *
 * MINING_ANALYSIS projects the minerals; the sale scenario asks QUOTES to net
 * the mineral's move against the dollar's. The dollar itself, with its series
 * and its bench of models, moved to «Factores externos y tipo de cambio»: it
 * belongs to the commercial side, and minerals is a different product.
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
    const state = { minerals: null, scenario: null, days: 30 };

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
        const days = Number(qs('#daysInput').value);
        if (!(days >= 1 && days <= 90)) {
            toast('El plazo debe estar entre 1 y 90 días.', 'error');
            return;
        }
        state.days = days;

        const done = setButtonBusy(qs('#runButton'), 'Proyectando…');
        qs('#errorState').hidden = true;
        try {
            await loadMinerals(days);
            qs('#mineralsPanel').hidden = false;
            qs('#scenarioPanel').hidden = false;
        } catch (error) {
            qs('#errorText').textContent = errorText(error, 'No se pudo consultar el servicio.');
            qs('#errorState').hidden = false;
        } finally {
            done();
        }
    }

    qs('#runButton').addEventListener('click', run);
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

    // The interpretation layer reads what each view is showing, as data.
    window.SD_AI.registerView('minerals_forecast', () => state.minerals);
    window.SD_AI.registerView('sale_scenario', () => ({
        minerals: state.minerals, scenario: state.scenario, days_ahead: state.days
    }));
    window.SD_AI.mountExplain('mineralsAi', 'minerals_forecast',
                             qs('#mineralsPanel').querySelector('.panel-head'));
    window.SD_AI.mountExplain('scenarioAi', 'sale_scenario',
                             qs('#scenarioPanel').querySelector('.panel-head'));

    run();
});
