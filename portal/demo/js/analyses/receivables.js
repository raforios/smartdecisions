'use strict';

/**
 * Cuentas por cobrar: position, aging, who owes, who collects and what
 * the rate took from the credit.
 */
(function (A) {
    if (!window.SD_AUTH.isAuthenticated()) return;
    const { qs, qsAll, toast, setButtonBusy } = window.SD_UI;

    // ---------- Receivables ----------
    // Backend codes, worded here. The service returns AgingBucket.DAYS_31_60
    // and CreditRisk.CRITICAL; the sentence belongs to the frontend.
    const AGING_LABELS = {
        CURRENT: 'Por vencer',
        DAYS_1_15: '1 a 15 días',
        DAYS_16_30: '16 a 30 días',
        DAYS_31_60: '31 a 60 días',
        DAYS_61_90: '61 a 90 días',
        DAYS_91_120: '91 a 120 días',
        DAYS_OVER_120: 'Más de 120 días'
    };

    const RISK_LABELS = {
        HEALTHY: 'Al día',
        WATCH: 'En observación',
        DELINQUENT: 'Moroso',
        CRITICAL: 'Crítico'
    };

    const DUE_WINDOW_LABELS = {
        OVERDUE: 'Ya vencido',
        DAYS_7: 'Próximos 7 días',
        DAYS_15: 'Días 8 a 15',
        DAYS_30: 'Días 16 a 30',
        BEYOND: 'Más adelante'
    };

    const RECEIVABLES_UNAVAILABLE = {
        NO_CREDIT_COLUMNS: 'Este archivo no trae las columnas de crédito ' +
            '(Condición Venta, Plazo Días). Descarga la plantilla actualizada, ' +
            'llénalas y vuelve a subir el archivo.',
        NO_CREDIT_SALES: 'Todas las ventas de este archivo son al contado, así que ' +
            'no hay cartera por cobrar que analizar.'
    };

    const CREDIT_MARGIN_UNAVAILABLE = {
        NO_COST_COLUMN: 'Sin el Costo Unitario cargado no se puede calcular qué deja ' +
            'el crédito: falta el margen del que se descuentan el financiamiento y el ' +
            'incobrable.'
    };

    function riskBadge(code) {
        return `<span class="badge badge-${String(code).toLowerCase()}">` +
               `${A.escapeHtml(RISK_LABELS[code] || code)}</span>`;
    }

    /**
     * The receivables book: position, aging, recoverability, who owes, who
     * collects, what falls due when and what the credit leaves.
     */
    /**
     * Rule 8: what the rate took from the credit. Each row is the same
     * bolivianos read at the day that matters to it; the losses carry no
     * bolivianos, because the balance never moved.
     */
    function renderCreditFx(fx) {
        const card = qs('#creditFxCard');
        card.hidden = !fx;
        if (!fx) return;
        const lossClass = (money) => ((money && money.usd) || 0) < 0 ? 'delta-down' : '';
        qs('#creditFxTable tbody').innerHTML = [
            ['Crédito dado, al tipo del día en que lo diste', fx.credit, ''],
            ['Cobrado, al tipo del día del crédito', fx.collected_at_credit, ''],
            ['Cobrado, al tipo del día del cobro', fx.collected_at_payment, ''],
            ['Se perdió en lo cobrado', fx.collected_lost, lossClass(fx.collected_lost)],
            ['Pendiente, al tipo del día del crédito', fx.open_at_credit, ''],
            ['Pendiente, al tipo de hoy', fx.open_today, ''],
            ['Se pierde en lo pendiente', fx.open_lost, lossClass(fx.open_lost)]
        ].map(([label, money, cls]) =>
            `<tr><td>${label}</td>${window.SD_MONEY.cells(money, 2, cls)}</tr>`).join('');
        window.SD_MONEY.expandHeaders(card);
    }

    function renderReceivables(data) {
        A.policyNotice('credit', 'stepReceivables', data.policy && data.policy.source_code);

        const empty = qs('#receivablesEmpty');
        const content = qs('#receivablesContent');

        if (!data || data.available !== true) {
            const code = data && data.reason_code;
            empty.textContent = RECEIVABLES_UNAVAILABLE[code] ||
                'Este archivo no tiene información de crédito para analizar.';
            empty.hidden = false;
            content.hidden = true;
            qs('#receivablesSubtitle').textContent = '';
            A.showPeriodBar(data && data.period);
            A.showAnalysisView('stepReceivables');
            return;
        }
        empty.hidden = true;
        content.hidden = false;

        const kpis = data.kpis || {};
        qs('#receivablesSubtitle').textContent =
            `Cartera al ${A.formatDate(kpis.as_of)}, el último día con movimiento del ` +
            'archivo. Todas las antigüedades se miden contra esa fecha. Se calcula en ' +
            `bolivianos; USD y USDT al tipo de hoy. ${window.SD_MONEY.ratesNote(data.rates)}`;

        A.fillKpis('receivablesKpis', [
            { label: 'Saldo por cobrar', value: kpis.receivable_total, format: 'money3',
              hint: `${A.formatInt(kpis.open_invoices)} facturas abiertas de ` +
                    `${A.formatInt(kpis.clients_with_debt)} clientes` },
            { label: 'Vencido', value: kpis.overdue_amount, format: 'money3',
              hint: `${A.formatDecimal(kpis.overdue_rate, 1)}% del saldo` },
            { label: 'Recuperable', value: kpis.recoverable_amount, format: 'money3',
              hint: `${A.formatDecimal(kpis.recoverable_rate, 1)}% del saldo` },
            { label: 'Incobrable estimado', value: kpis.uncollectible_amount,
              format: 'money3',
              hint: `${A.formatDecimal(kpis.uncollectible_rate, 1)}% del saldo` },
            { label: 'Venta a crédito', value: kpis.credit_share, format: 'percent',
              hint: `${window.SD_MONEY.inline(kpis.credit_amount)} de la venta del período` },
            { label: 'DSO', value: kpis.days_sales_outstanding, format: 'decimal',
              hint: 'Días que tarda en volver la venta a crédito' },
            { label: 'Mora promedio', value: kpis.weighted_days_late, format: 'decimal',
              hint: 'Días de atraso de lo vencido, ponderados por monto' },
            { label: 'Efectividad de cobranza', value: kpis.collection_effectiveness,
              format: 'decimal',
              hint: 'CEI: de lo cobrable en el período, cuánto se cobró (100 es todo)' },
            { label: 'Cobrado a tiempo', value: kpis.on_time_rate, format: 'percent',
              hint: 'Parte de lo ya cobrado que entró dentro del plazo' },
            { label: 'Plazo otorgado vs real', value: kpis.average_term_granted,
              format: 'decimal',
              hint: kpis.average_term_real == null
                  ? 'Todavía no hay cobros para comparar'
                  : `Se cobra en promedio a los ${A.formatDecimal(kpis.average_term_real, 1)} días` }
        ]);

        renderReceivablesPolicy(data.policy);
        renderCreditFx(data.devaluation);
        renderAging(data.aging || []);
        renderCreditMargin(data.margin || {});

        A.fillTable('debtorsTable', data.debtors, (row) =>
            `<td>${A.escapeHtml(row.label)}</td>` +
            window.SD_MONEY.cells(row.open_amount) +
            window.SD_MONEY.cells(row.overdue_amount) +
            `<td class="numeric">${A.formatInt(row.oldest_days)}</td>` +
            `<td class="numeric">${row.limit_utilization == null
                ? '<span class="cell-note">sin línea</span>'
                : `${A.formatDecimal(row.limit_utilization, 1)}%`}</td>` +
            `<td>${riskBadge(row.risk_code)}</td>`);

        A.fillTable('collectorsTable', data.collectors, (row) =>
            `<td>${A.escapeHtml(row.label)}</td>` +
            window.SD_MONEY.cells(row.open_amount) +
            window.SD_MONEY.cells(row.overdue_amount) +
            `<td class="numeric">${A.formatInt(row.clients)}</td>` +
            `<td class="numeric">${row.on_time_rate == null
                ? '—' : `${A.formatDecimal(row.on_time_rate, 1)}%`}</td>`);

        renderDueCalendar(data.due_windows || [], data.due_dates || []);
        renderCollectionCurve(data.collection_curve || []);

        A.fillTable('priorityTable', data.priority, (row) =>
            `<td>${A.escapeHtml(row.label)}</td>` +
            `<td>${A.escapeHtml(row.collector || '—')}</td>` +
            window.SD_MONEY.cells(row.overdue_amount) +
            `<td class="numeric">${A.formatInt(row.oldest_days)}</td>` +
            `<td class="numeric">${A.formatDecimal(row.recovery_probability * 100, 0)}%</td>` +
            window.SD_MONEY.cells(row.expected_recovery));

        A.showPeriodBar(data.period);
        A.showAnalysisView('stepReceivables');
    }

    function renderReceivablesPolicy(policy) {
        if (!policy) {
            qs('#receivablesPolicyNote').textContent = '';
            return;
        }
        const own = policy.source_code === 'CLIENT';
        qs('#receivablesPolicyNote').textContent =
            (own ? 'Calculado con tu política de crédito' : 'Calculado con la política por defecto') +
            `: tramos de ${policy.aging_buckets.join(', ')} días, ` +
            `tasa financiera ${A.formatDecimal(policy.financial_rate_daily * 365 * 100, 1)}% anual` +
            (own ? '.' : '. Puedes registrar la tuya y estos números cambian.');
    }

    function renderAging(aging) {
        A.makeChart('chartAging', {
            type: 'bar',
            data: {
                labels: aging.map((row) => AGING_LABELS[row.bucket_code] || row.bucket_code),
                datasets: [{
                    label: `Saldo (${A.chartSymbol()})`,
                    data: aging.map((row) => A.chartAmount(row.amount)),
                    backgroundColor: aging.map((row) =>
                        row.bucket_code === 'CURRENT' ? A.BRAND[3] : A.BRAND[1])
                }]
            },
            options: A.chartOptions('chartMoney')
        });

        const recoverable = aging.map((row) =>
            A.chartAmount(row.amount) - A.chartAmount(row.provision));
        A.makeChart('chartRecovery', {
            type: 'bar',
            data: {
                labels: aging.map((row) => AGING_LABELS[row.bucket_code] || row.bucket_code),
                datasets: [
                    { label: 'Recuperable', data: recoverable, backgroundColor: A.BRAND[3] },
                    {
                        label: 'Incobrable', backgroundColor: A.BRAND[1],
                        data: aging.map((row) => A.chartAmount(row.provision))
                    }
                ]
            },
            options: {
                responsive: true,
                plugins: { legend: { position: 'bottom' } },
                scales: { x: { stacked: true }, y: { stacked: true } }
            }
        });

        A.fillTable('agingTable', aging, (row) =>
            `<td>${A.escapeHtml(AGING_LABELS[row.bucket_code] || row.bucket_code)}</td>` +
            `<td class="numeric">${A.formatInt(row.invoices)}</td>` +
            `<td class="numeric">${A.formatInt(row.clients)}</td>` +
            window.SD_MONEY.cells(row.amount) +
            `<td class="numeric">${A.formatDecimal(row.share, 1)}%</td>` +
            `<td class="numeric">${A.formatDecimal(row.expected_loss_rate * 100, 0)}%</td>` +
            window.SD_MONEY.cells(row.provision));
    }

    function renderCreditMargin(margin) {
        const block = qs('#creditMarginBlock');
        if (!margin.available) {
            block.hidden = false;
            qs('#creditMarginKpis').innerHTML = '';
            qs('#creditMarginNote').textContent =
                CREDIT_MARGIN_UNAVAILABLE[margin.reason_code] ||
                'No hay datos suficientes para calcular qué deja el crédito.';
            return;
        }
        block.hidden = false;

        A.fillKpis('creditMarginKpis', [
            { label: 'Margen bruto del crédito', value: margin.credit_gross_margin,
              format: 'money3',
              hint: `${A.formatDecimal(margin.credit_gross_margin_rate, 1)}% de la venta a ` +
                    `crédito · al contado ${A.formatDecimal(margin.cash_gross_margin_rate, 1)}%` },
            { label: 'Costo financiero', value: margin.financing_cost, format: 'money3',
              hint: `De los cuales ${window.SD_MONEY.inline(margin.delinquency_cost)} son ` +
                    'por mora' },
            { label: 'Incobrable esperado', value: margin.expected_loss, format: 'money3',
              hint: 'Provisión sobre el saldo abierto' },
            { label: 'Margen neto del crédito', value: margin.net_margin, format: 'money3',
              hint: `${A.formatDecimal(margin.net_margin_rate, 1)}% de la venta a crédito` }
        ]);

        const lost = window.SD_MONEY.minus(margin.credit_gross_margin, margin.net_margin);
        qs('#creditMarginNote').textContent =
            `Financiar y provisionar la cartera se lleva ${window.SD_MONEY.inline(lost)} ` +
            `del margen bruto: de ${A.formatDecimal(margin.credit_gross_margin_rate, 1)}% ` +
            `queda ${A.formatDecimal(margin.net_margin_rate, 1)}%.`;
    }

    function renderDueCalendar(windows, dates) {
        A.makeChart('chartDueWindows', {
            type: 'bar',
            data: {
                labels: windows.map((row) => DUE_WINDOW_LABELS[row.window_code] || row.window_code),
                datasets: [{
                    label: `Monto (${A.chartSymbol()})`,
                    data: windows.map((row) => A.chartAmount(row.amount)),
                    backgroundColor: windows.map((row) =>
                        row.window_code === 'OVERDUE' ? A.BRAND[1] : A.BRAND[0])
                }]
            },
            options: A.chartOptions('chartMoney')
        });

        A.fillTable('dueDatesTable', dates, (row) =>
            `<td>${A.escapeHtml(A.formatDate(row.due_date))}</td>` +
            window.SD_MONEY.cells(row.amount) +
            `<td class="numeric">${A.formatInt(row.invoices)}</td>` +
            `<td class="numeric">${A.formatInt(row.clients)}</td>`);
    }

    function renderCollectionCurve(curve) {
        qs('#curveCard').hidden = curve.length === 0;
        if (!curve.length) return;

        A.makeChart('chartCurve', {
            type: 'line',
            data: {
                labels: curve.map((point) => point.cohort_month),
                datasets: [30, 60, 90].map((days, index) => ({
                    label: `${days} días`,
                    data: curve.map((point) => point[`collected_${days}`]),
                    borderColor: [A.BRAND[0], A.BRAND[3], A.BRAND[2]][index],
                    backgroundColor: 'transparent',
                    // A horizon that has not elapsed travels as null: the line
                    // breaks instead of dropping to zero, which would read as a crash.
                    spanGaps: false, tension: 0.3
                }))
            },
            options: {
                responsive: true,
                plugins: { legend: { position: 'bottom' } },
                scales: { y: { ticks: { callback: (value) => `${Number(value).toLocaleString('es-BO')}%` } } }
            }
        });
    }

    Object.assign(A, {
        renderAging, renderDueCalendar, renderReceivables
    });
})(window.SD_ANALYSIS = window.SD_ANALYSIS || {});
