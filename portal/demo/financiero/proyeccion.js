'use strict';

/**
 * Proyección: the three scenarios of the plan. The percentages and the
 * horizon start from the defaults FINANCE reads from its own table and the
 * manager can type others; FINANCE validates them and recalculates
 * (Rafael, 17-oct). Future months have no exchange rate yet: they are read
 * at today's.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.isAuthenticated()) return;

    const F = window.SD_FINANCE;
    const { qs, toast, setButtonBusy } = window.SD_UI;
    const css = getComputedStyle(document.documentElement);
    const color = (name) => css.getPropertyValue(name).trim();
    const NAMES = { WORST: 'Peor', REALISTIC: 'Realista', BEST: 'Mejor' };
    // The model ML_FUNCTIONS chose for the net sales, in the owner's words.
    const MODELS = {
        NAIVE: 'el mes que viene igual que el último, porque ningún modelo lo hizo mejor',
        DAMPED_TREND: 'tendencia amortiguada',
        HOLT_WINTERS: 'tendencia amortiguada con la estacionalidad de tus meses'
    };
    const COLORS = { WORST: '--danger', REALISTIC: '--accent', BEST: '--success' };
    const FIELDS = { horizon: 'horizon', worst_sales: 'worstSales', worst_outflow: 'worstOutflow',
                     best_sales: 'bestSales', best_outflow: 'bestOutflow' };
    const fmt = (value) => value == null ? '—' : Number(value).toLocaleString('es-BO',
        { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    const state = { data: null, chart: null };

    /** The month before `key`, in words: «alcanza hasta enero de 2027». */
    function lastGoodMonth(key) {
        const [year, month] = key.split('-').map(Number);
        const previous = month === 1 ? `${year - 1}-12` : `${year}-${String(month - 1).padStart(2, '0')}`;
        return F.periodLabel(previous);
    }

    function cards(data) {
        F.arrange(qs('#scenarioCards'), data.scenarios.map((scenario) => {
            const last = scenario.months[scenario.months.length - 1];
            const node = document.createElement('div');
            node.className = 'metric';
            const verdict = scenario.cash_runs_out
                ? (scenario.cash_runs_out === scenario.months[0].period
                    ? 'El efectivo no alcanza ni para el primer mes.'
                    : `El efectivo alcanza hasta ${lastGoodMonth(scenario.cash_runs_out)}.`)
                : `El efectivo dura los ${data.horizon} meses.`;
            node.innerHTML = `<p class="metric-label">${NAMES[scenario.name]} · ventas ` +
                `${scenario.sales_change > 0 ? '+' : ''}${scenario.sales_change} %, egresos ` +
                `${scenario.outflow_change > 0 ? '+' : ''}${scenario.outflow_change} %</p>` +
                `<p class="metric-value ${scenario.cash_runs_out ? 'negative' : 'positive'}">${verdict}</p>` +
                window.SD_MONEY.card(F.money(last.cash, data.exchange)) +
                `<p class="metric-hint">Efectivo disponible al cierre de ${F.periodLabel(last.period)}.</p>`;
            return node;
        }));
    }

    function chart(data) {
        if (!window.Chart) return;
        window.Chart.defaults.maintainAspectRatio = false;
        window.Chart.defaults.locale = 'es-BO';
        if (state.chart) state.chart.destroy();
        state.chart = new window.Chart(qs('#cashChart'), {
            type: 'line',
            data: {
                labels: data.scenarios[0].months.map((m) => F.periodLabel(m.period)),
                datasets: data.scenarios.map((scenario) => ({
                    label: NAMES[scenario.name], data: scenario.months.map((m) => m.cash),
                    borderColor: color(COLORS[scenario.name]),
                    backgroundColor: color(COLORS[scenario.name]), tension: 0.2
                }))
            },
            options: { responsive: true, plugins: { legend: { position: 'bottom' } } }
        });
    }

    function table() {
        const data = state.data;
        const scenario = data.scenarios.find((s) => s.name === qs('#scenarioSelect').value);
        qs('#monthsTable tbody').innerHTML = scenario.months.map((m) => {
            const cash = F.money(m.cash, data.exchange);
            return `<tr><td>${F.periodLabel(m.period)}</td><td class="numeric">${fmt(m.net_sales)}</td>` +
                `<td class="numeric">${fmt(m.outflow)}</td><td class="numeric">${fmt(m.profit)}</td>` +
                `<td class="numeric">${m.income_tax_paid ? fmt(m.income_tax_paid) : ''}</td>` +
                `<td class="numeric">${fmt(m.reserve)}</td><td class="numeric">${fmt(cash.bob)}</td>` +
                `<td class="numeric">${fmt(cash.usd)}</td><td class="numeric">${fmt(cash.usdt)}</td></tr>`;
        }).join('');
    }

    function fillInputs(data) {
        const of = (name) => data.scenarios.find((s) => s.name === name);
        qs('#horizon').value = data.horizon;
        qs('#worstSales').value = of('WORST').sales_change;
        qs('#worstOutflow').value = of('WORST').outflow_change;
        qs('#bestSales').value = of('BEST').sales_change;
        qs('#bestOutflow').value = of('BEST').outflow_change;
    }

    function render(data) {
        state.data = data;
        qs('#notices').innerHTML = F.noticesHtml(data.notices);
        if (!data.scenarios.length) {
            qs('#scenarioCards').innerHTML = '';
            qs('#monthsTable tbody').innerHTML = '';
            return;
        }
        fillInputs(data);
        const model = data.model;
        const measured = model.tested_points
            ? ` Probado en tus últimos ${model.tested_points} meses: erró ` +
              `±${fmt(model.error_percent)} %; «el mes que viene igual que este» habría errado ` +
              `±${fmt(model.naive_error_percent)} %.`
            : ' Todavía no hay meses suficientes para medir su error.';
        qs('#modelLine').textContent = `Escenario realista: ${MODELS[model.name] || MODELS.NAIVE}, ` +
            `sobre tus meses cargados hasta ${F.periodLabel(data.last_period)}.${measured}`;
        qs('#ratesLine').textContent = data.exchange
            ? `Los meses futuros se leen al tipo de cambio de hoy. ${F.ratesLine(data.exchange)}`
            : F.ratesLine(null);
        cards(data);
        chart(data);
        table();
    }

    async function load(query) {
        const done = setButtonBusy(qs('#scenarioRun'), 'Calculando…');
        try {
            render(await F.get('/projection', query));
        } catch (error) {
            toast(F.errorText(error, 'No se pudo calcular la proyección.'), 'error');
        } finally {
            done();
        }
    }

    qs('#scenarioForm').addEventListener('submit', (event) => {
        event.preventDefault();
        const query = {};
        Object.entries(FIELDS).forEach(([param, id]) => {
            const value = qs(`#${id}`).value.trim();
            if (value !== '') query[param] = value;
        });
        load(query);
    });
    qs('#scenarioReset').addEventListener('click', () => load());
    qs('#scenarioSelect').addEventListener('change', () => state.data && table());

    // The AI reads the whole projection as the backend answered it: the three
    // scenarios, the model's error and the notices.
    F.explain('finance_projection', () => state.data, qs('#scenarioForm'));
    load();
});
