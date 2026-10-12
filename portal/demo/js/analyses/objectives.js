'use strict';

/**
 * Cumplimiento de objetivos: invoiced and collected against target.
 */
(function (A) {
    if (!window.SD_AUTH.isAuthenticated()) return;
    const { qs, qsAll, toast, setButtonBusy } = window.SD_UI;

    // The backend codes; the color and the word belong to the frontend,
    // which is where they should be.
    const SEMAPHORE_LABEL = { GREEN: 'Verde', YELLOW: 'Amarillo', RED: 'Rojo' };
    const SEMAPHORE_COLOR = { GREEN: '#2d7d46', YELLOW: '#c4a378', RED: '#c0392b' };
    const SEMAPHORE_ORDER = ['GREEN', 'YELLOW', 'RED'];

    function semaphoreTag(code) {
        const color = SEMAPHORE_COLOR[code] || '#5e6580';
        return `<span class="badge" style="background:${color}">` +
            `${A.escapeHtml(SEMAPHORE_LABEL[code] || code || '—')}</span>`;
    }

    /**
     * Attainment against target: how much was sold against what should have
     * been sold, per client and per month, with the invoiced and the collected
     * traffic lights, which are not the same question.
     */
    function renderObjectives(data) {
        A.policyNotice('commercial', 'stepObjectives');

        const empty = qs('#objectivesEmpty');
        const content = qs('#objectivesContent');
        const totals = (data && data.totals) || {};

        if (!data || !data.clients || data.clients.length === 0) {
            const sinObjetivo = (data && data.clients_without_objective) || 0;
            empty.textContent = sinObjetivo > 0
                ? `Todavía no cargaste objetivos. Hay ${A.formatInt(sinObjetivo)} ` +
                  'cliente(s) con ventas esperando una meta contra la cual medirse. ' +
                  'Descarga la plantilla «objetivos» y cárgala para ver esta vista.'
                : 'Todavía no cargaste objetivos para este archivo.';
            empty.hidden = false;
            content.hidden = true;
            qs('#objectivesSubtitle').textContent = '';
            A.showPeriodBar(data && data.period);
            A.showAnalysisView('stepObjectives');
            return;
        }
        empty.hidden = true;
        content.hidden = false;

        const meses = totals.periods || [];
        const disponibles = data.available_periods || [];
        // With no period chosen the service judges only the last month: it is
        // said, so the manager knows the dates above can widen it.
        const alcance = meses.length === 1
            ? `en ${meses[0]}`
            : `en ${meses.length} meses, de ${meses[0] || '—'} a ${meses[meses.length - 1] || '—'}`;
        const ampliar = disponibles.length > meses.length
            ? ` Hay ${disponibles.length} meses cargados (${disponibles[0]} a ` +
              `${disponibles[disponibles.length - 1]}): elige otro período arriba para verlos.`
            : '';
        qs('#objectivesSubtitle').textContent =
            `${A.formatInt(totals.clients_count)} clientes con objetivo ${alcance}.` + ampliar +
            (data.clients_without_objective
                ? ` Otros ${A.formatInt(data.clients_without_objective)} facturaron ` +
                  'sin objetivo asignado: no se los puntúa, porque no hay meta ' +
                  'contra la cual compararlos.'
                : '') +
            ` Se mide en bolivianos; USD y USDT al tipo de hoy. ${window.SD_MONEY.ratesNote(data.rates)}`;

        A.fillKpis('objectivesKpis', [
            { label: 'Objetivo', value: totals.target_amount, format: 'money3',
              hint: 'Lo que la empresa decidió vender en el período' },
            { label: 'Facturado', value: totals.invoiced_amount, format: 'money3',
              hint: `${A.formatDecimal(totals.invoiced_ratio * 100, 1)}% del objetivo` },
            { label: 'Cobrado', value: totals.collected_amount, format: 'money3',
              hint: `${A.formatDecimal(totals.collected_ratio * 100, 1)}% del objetivo` },
            { label: 'Deuda', value: totals.debt_amount, format: 'money3',
              hint: `${A.formatDecimal(totals.debt_ratio * 100, 1)}% del objetivo — ` +
                    'facturado que todavía no se cobró' },
            { label: 'Puntos', value: totals.points, format: 'decimal',
              hint: 'A la tasa de cada cluster' }
        ]);

        const policy = data.policy || {};
        qs('#objectivesPolicyNote').textContent =
            `Semáforo: rojo por debajo de ` +
            `${A.formatDecimal((policy.yellow_from || 0) * 100, 0)}%, amarillo hasta ` +
            `${A.formatDecimal((policy.green_from || 0) * 100, 0)}%, verde desde ahí. ` +
            'Son parámetros de tu política comercial, no del sistema.';

        renderSemaphoreCharts(data.clients || [], data.by_cluster || []);
        renderObjectivesTables(data);
        A.showPeriodBar(data.period);
        A.showAnalysisView('stepObjectives');
    }

    function renderSemaphoreCharts(clients, cells) {
        const counts = {};
        const weights = {};
        clients.forEach((row) => {
            counts[row.invoiced_semaphore] = (counts[row.invoiced_semaphore] || 0) + 1;
        });
        cells.forEach((cell) => {
            weights[cell.semaphore] = (weights[cell.semaphore] || 0) + cell.weight_on_target;
        });
        const codes = SEMAPHORE_ORDER.filter((code) => counts[code] || weights[code]);

        A.makeChart('chartSemaphore', {
            type: 'doughnut',
            data: {
                labels: codes.map((code) => `${SEMAPHORE_LABEL[code]} (${counts[code] || 0})`),
                datasets: [{ data: codes.map((code) => counts[code] || 0),
                    backgroundColor: codes.map((code) => SEMAPHORE_COLOR[code]) }]
            },
            options: { responsive: true, plugins: { legend: { position: 'right' } } }
        });

        A.makeChart('chartSemaphoreWeight', {
            type: 'doughnut',
            data: {
                labels: codes.map((code) =>
                    `${SEMAPHORE_LABEL[code]} (${A.formatDecimal((weights[code] || 0) * 100, 1)}%)`),
                datasets: [{ data: codes.map((code) => (weights[code] || 0) * 100),
                    backgroundColor: codes.map((code) => SEMAPHORE_COLOR[code]) }]
            },
            options: { responsive: true, plugins: { legend: { position: 'right' } } }
        });
    }

    function renderObjectivesTables(data) {
        A.fillTable('objectivesClusterTable', data.by_cluster || [], (cell) =>
            `<td>${A.escapeHtml(cell.cluster)}</td>` +
            `<td>${semaphoreTag(cell.semaphore)}</td>` +
            `<td class="num">${A.formatInt(cell.clients_count)}</td>` +
            window.SD_MONEY.cells(cell.target_amount, 0) +
            window.SD_MONEY.cells(cell.invoiced_amount, 0) +
            window.SD_MONEY.cells(cell.debt_amount, 0) +
            `<td class="num">${A.formatDecimal(cell.invoiced_ratio * 100, 1)}%</td>` +
            `<td class="num">${A.formatDecimal(cell.weight_on_target * 100, 1)}%</td>`,
            { emptyText: 'Sin celdas para mostrar.' });

        // Largest objective first: the clients that weigh most on the target
        // lead the list, whether they met it or not (Rafael, 12-oct).
        const clients = (data.clients || []).slice()
            .sort((a, b) => window.SD_MONEY.bob(b.target_amount) -
                window.SD_MONEY.bob(a.target_amount));

        A.fillTable('objectivesClientTable', clients, (row) =>
            `<td>${A.escapeHtml(row.pos_name || row.pos_id)}</td>` +
            `<td>${A.escapeHtml(row.period)}</td>` +
            `<td>${A.escapeHtml(row.cluster || '—')}</td>` +
            window.SD_MONEY.cells(row.target_amount, 0) +
            window.SD_MONEY.cells(row.invoiced_amount, 0) +
            `<td class="num">${semaphoreTag(row.invoiced_semaphore)} ` +
            `${A.formatDecimal(row.invoiced_ratio * 100, 1)}%</td>` +
            window.SD_MONEY.cells(row.collected_amount, 0) +
            `<td class="num">${semaphoreTag(row.collected_semaphore)} ` +
            `${A.formatDecimal(row.collected_ratio * 100, 1)}%</td>` +
            window.SD_MONEY.cells(row.debt_amount, 0) +
            `<td class="num">${A.formatDecimal(row.points, 0)}</td>`,
            { emptyText: 'Sin clientes con objetivo.' });
    }

    Object.assign(A, {
        renderObjectives
    });
})(window.SD_ANALYSIS = window.SD_ANALYSIS || {});
