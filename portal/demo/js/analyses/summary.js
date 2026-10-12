'use strict';

/**
 * Resumen Comercial and Fuente de volumen: one response, two views, with
 * margin, growth, concentration, efficiency and the chosen month.
 */
(function (A) {
    if (!window.SD_AUTH.isAuthenticated()) return;
    const { qs, qsAll, toast, setButtonBusy } = window.SD_UI;

    /**
     * The commercial summary and the volume source come from the same response.
     * `view` says which view to end on, because the user may have asked for
     * either one and the file is read only once.
     */
    function renderCommercialSummary(data, view) {
        // A chosen month reads at its close; its cards add the same at today.
        A.monthTodayRates = data.chosen_month ? data.chosen_month.today_rates : null;
        // KPIs
        A.fillKpis('dashboardKpis', data.kpis, (card) =>
            card.metric_code === 'TOTAL_SALES' ? 'success' : '');

        renderSummaryCharts(data);

        A.showPeriodBar(data.period);
        renderMargin(data.margin);
        renderGrowth(data.growth);
        renderVolumeSource(data.volume_source);
        renderConcentration(data.concentration);
        renderEfficiency(data.efficiency);
        renderChosenMonth(data.chosen_month);
        A.monthTodayRates = null;

        A.showAnalysisView(view || 'stepDashboard');
    }

    /**
     * A chosen month against today: its total at the close, the same at
     * today's rate and the difference; then its days, each at the rate of its
     * own day. The days' dollars may not add up to the month's: by rule they
     * are history and are not adjusted.
     */
    function renderChosenMonth(month) {
        const card = qs('#chosenMonthCard');
        card.hidden = !month;
        if (!month) return;
        const rate = (rates) => `oficial Bs ${A.formatDecimal(rates.usd, 2)} · ` +
            `USDT Bs ${A.formatDecimal(rates.usdt, 2)}`;
        const name = A.formatDateMonth(month.month);
        qs('#chosenMonthTitle').textContent =
            `${name.charAt(0).toUpperCase()}${name.slice(1)} frente a hoy`;
        qs('#chosenMonthRates').textContent =
            `Cierre del mes: ${rate(month.close_rates)}. Hoy: ${rate(month.today_rates)}.`;
        qs('#chosenMonthTotals tbody').innerHTML = [
            ['Al cierre del mes', month.total, ''],
            ['A hoy', month.total_today, ''],
            ['Diferencia', month.difference,
                (month.difference.usd || 0) < 0 ? 'delta-down' : 'delta-up']
        ].map(([label, money, cls]) =>
            `<tr><td>${label}</td>${window.SD_MONEY.cells(money, 2, cls)}</tr>`).join('');
        A.fillTable('chosenMonthDays', month.days, (day) =>
            `<td>${A.formatDate(day.date)}</td>${window.SD_MONEY.cells(day.amount, 2)}`,
            { emptyText: 'Sin ventas en el mes.' });
        qs('#chosenMonthDaysTotal').innerHTML =
            `Suma de los días, cada uno a su tipo: ${window.SD_MONEY.inline(month.days_total, 2)}. ` +
            'Puede no coincidir con el total del mes en dólares; no se ajusta.';
        window.SD_MONEY.expandHeaders(card);
    }

    /** Every chart of the summary that draws money, in the chart currency. */
    function renderSummaryCharts(data) {
        const trend = data.monthly_trend || [];
        A.makeChart('chartTrend', {
            type: 'line',
            data: {
                labels: trend.map((p) => p.month),
                datasets: [{
                    label: `Venta (${A.chartSymbol()})`, data: trend.map((p) => A.chartAmount(p.amount)),
                    borderColor: A.BRAND[0], backgroundColor: 'rgba(13,30,76,0.1)',
                    fill: true, tension: 0.3
                }]
            },
            options: A.chartOptions('chartMoney')
        });

        const cat = data.by_category || [];
        A.makeChart('chartCategoria', {
            type: 'doughnut',
            data: {
                labels: cat.map((c) => A.dimensionLabel(c.label)),
                datasets: [{ data: cat.map((c) => A.chartAmount(c.amount)), backgroundColor: A.BRAND }]
            },
            options: { responsive: true, plugins: { legend: { position: 'right' } } }
        });

        const sales = `Venta (${A.chartSymbol()})`;
        A.horizontalBar('chartTopProductos', data.top_products, sales);
        A.horizontalBar('chartTopClientes', data.best_clients, sales);
        A.horizontalBar('chartVendedor', (data.by_seller || []).slice(0, 10), sales);
        // Bottom products: same bars as the top ten, so the two read alike.
        A.horizontalBar('chartBottomProductos', data.bottom_products, sales);

        if (data.margin && data.margin.available) {
            renderMarginChart(data.margin.by_category || []);
        }
        renderAbcChart((data.volume_source && data.volume_source.abc_summary) || []);
    }

    function renderMarginChart(categories) {
        A.makeChart('chartMargenCategoria', {
            type: 'bar',
            data: {
                labels: categories.map((row) => A.dimensionLabel(row.label)),
                datasets: [
                    {
                        label: `Venta (${A.chartSymbol()})`,
                        data: categories.map((row) => A.chartAmount(row.amount)),
                        backgroundColor: A.BRAND[5]
                    },
                    {
                        label: `Margen (${A.chartSymbol()})`,
                        data: categories.map((row) => A.chartAmount(row.margin)),
                        backgroundColor: A.BRAND[3]
                    }
                ]
            },
            options: {
                responsive: true,
                plugins: { legend: { position: 'bottom' } },
                scales: { x: { stacked: false } }
            }
        });
    }

    // ---------- Profitability ----------
    function renderMargin(margen) {
        // Hidden rather than zeroed: a file without unit costs has no margin,
        // and "0%" would read as "you earn nothing".
        const block = qs('#marginBlock');
        if (!margen || !margen.available) {
            block.hidden = true;
            return;
        }
        block.hidden = false;

        A.fillKpis('marginKpis', margen.kpis, (card) =>
            card.metric_code === 'GROSS_MARGIN' ? 'success' : '');

        const categories = margen.by_category || [];
        A.fillTable('marginCategoryTable', categories, (row) =>
            `<td>${A.escapeHtml(A.dimensionLabel(row.label))}</td>` +
            window.SD_MONEY.cells(row.amount) +
            window.SD_MONEY.cells(row.margin, 2, 'hero') +
            `<td class="numeric">${A.formatDecimal(row.margin_percentage, 1)}%</td>`);

        const alerts = margen.alerts || [];
        qs('#marginAlerts').hidden = alerts.length === 0;
        A.fillTable('marginAlertTable', alerts, (row) =>
            `<td>${A.escapeHtml(A.dimensionLabel(row.label))}</td>` +
            window.SD_MONEY.cells(row.amount) +
            window.SD_MONEY.cells(row.margin, 2, 'delta-down') +
            `<td>${A.escapeHtml(A.MARGIN_ALERT_REASONS[row.reason_code] || '')}</td>`);
    }

    // ---------- Growth ----------
    function renderGrowth(crecimiento) {
        const block = qs('#growthBlock');
        const series = (crecimiento && crecimiento.monthly_change) || [];
        if (!series.length) {
            block.hidden = true;
            return;
        }
        block.hidden = false;

        A.fillKpis('growthKpis', crecimiento.kpis, (card) => {
            if (card.format !== 'percent' || card.value == null) return '';
            return card.value >= 0 ? 'success' : 'warning';
        });

        A.makeChart('chartGrowth', {
            type: 'bar',
            data: {
                labels: series.map((point) => point.month),
                datasets: [{
                    label: 'Variación (%)',
                    data: series.map((point) => point.change),
                    backgroundColor: series.map((point) =>
                        (point.change || 0) >= 0 ? A.BRAND[3] : '#c0392b')
                }]
            },
            options: A.chartOptions('percent')
        });

        // Seasonality needs a full year of history; without it the engine sends
        // nothing and the card would otherwise render an empty canvas.
        const seasonality = crecimiento.seasonality || [];
        qs('#seasonalityCard').hidden = seasonality.length === 0;
        if (seasonality.length) {
            A.makeChart('chartSeasonality', {
                type: 'line',
                data: {
                    labels: seasonality.map((row) => row.month),
                    datasets: [{
                        label: 'Índice', data: seasonality.map((row) => row.index_value),
                        borderColor: A.BRAND[1], backgroundColor: 'rgba(122,74,42,0.12)',
                        fill: true, tension: 0.35
                    }]
                },
                options: A.chartOptions('decimal')
            });
        }

    }

    // ---------- Volume source ----------
    // Codes the engine reports, worded here. The backend names the effect;
    // the sentence that explains it belongs to the frontend.
    const VOLUME_EFFECTS = {
        PRICE: ['Precio', 'Lo mismo vendido a otro precio'],
        QUANTITY: ['Cantidad', 'Más o menos unidades al precio anterior'],
        JOINT: ['Cruce', 'La parte que no es sólo precio ni sólo cantidad'],
        ENTRY: ['Productos nuevos', 'Productos que no se vendían el mes anterior'],
        EXIT: ['Productos que salieron', 'Productos que dejaron de venderse'],
        NEW_CLIENTS: ['Clientes nuevos', 'Cuentas que no compraban el mes anterior'],
        LOST_CLIENTS: ['Clientes perdidos', 'Cuentas que dejaron de comprar'],
        RETAINED_CLIENTS: ['Clientes que se mantuvieron', 'Los mismos clientes, comprando distinto']
    };

    function effectLabel(code) {
        const entry = VOLUME_EFFECTS[code];
        return entry ? entry[0] : String(code);
    }

    function effectHint(code) {
        const entry = VOLUME_EFFECTS[code];
        return entry ? entry[1] : '';
    }

    function fillEffects(tableId, rows) {
        A.fillTable(tableId, rows, (row) =>
            `<td>${A.escapeHtml(effectLabel(row.effect_code))}` +
            `<span class="cell-note">${A.escapeHtml(effectHint(row.effect_code))}</span></td>` +
            window.SD_MONEY.cells(row.amount, 2, A.deltaClass(window.SD_MONEY.pick(row.amount, 'BOB'))) +
            `<td class="numeric">${A.formatDelta(row.percentage)}</td>`);
    }

    /**
     * Where the volume comes from: products, clients, the cross between both
     * and the breakdown of the latest movement.
     *
     * The pieces that used to be scattered —the category mix inside Growth and
     * the ABC inside Concentration— are shown here and only here.
     */
    function renderVolumeSource(volumen) {
        const headline = (volumen && volumen.headline) || {};
        // With no products there is nothing to answer, but the view still
        // shows with its explanation: if the user asked for this analysis,
        // leaving them in front of a blank screen is worse than saying why.
        const empty = !headline.total_products;
        qs('#volumeEmpty').hidden = !empty;
        qs('#volumeContent').hidden = empty;
        if (empty) return;

        A.fillKpis('volumeKpis', [
            { label: 'Productos vendidos', value: headline.total_products, format: 'int',
              hint: 'Cuántos productos distintos tuvieron venta en el período' },
            { label: 'Productos que hacen el 80%', value: headline.pareto_products,
              format: 'int',
              hint: `El ${A.formatDecimal(headline.pareto_product_percentage, 1)}% del catálogo` },
            { label: `Peso del top ${headline.top_products_count}`,
              value: headline.top_products_percentage, format: 'percent',
              hint: 'Qué parte de la venta hacen los productos de la tabla' }
        ]);

        A.setLevelReading('volumeHhiReading', headline.hhi_level, A.VOLUME_LEVELS);

        const products = volumen.products || [];
        A.makeChart('chartVolumePareto', {
            type: 'bar',
            data: {
                labels: products.map((row) => A.shortLabel(row.label)),
                datasets: [
                    {
                        label: 'Participación', data: products.map((row) => row.share),
                        backgroundColor: A.BRAND[0], order: 2
                    },
                    {
                        label: 'Acumulado', type: 'line', order: 1,
                        data: products.map((row) => row.cumulative),
                        borderColor: A.BRAND[3], backgroundColor: 'rgba(45,125,70,0.1)',
                        tension: 0.3, pointRadius: 2
                    }
                ]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { display: true, position: 'bottom' },
                    tooltip: {
                        callbacks: {
                            title: (items) => products[items[0].dataIndex].label,
                            label: (ctx) => `${ctx.dataset.label}: ` +
                                `${A.formatDecimal(ctx.parsed.y, 2)}%`
                        }
                    }
                },
                scales: { y: { ticks: { callback: (value) => `${Number(value).toLocaleString('es-BO')}%` } } }
            }
        });

        A.fillTable('volumeProductsTable', products, (row) =>
            `<td>${A.escapeHtml(row.label)}</td>` +
            window.SD_MONEY.cells(row.amount) +
            `<td class="numeric">${A.formatDecimal(row.share, 2)}%</td>` +
            `<td class="numeric">${A.formatDecimal(row.cumulative, 2)}%</td>` +
            `<td><span class="badge badge-${row.abc_class.toLowerCase()}">` +
            `${row.abc_class}</span></td>` +
            `<td class="numeric">${A.formatInt(row.clients)}</td>`);

        A.fillTable('volumeClientsTable', volumen.clients, (row) =>
            `<td>${A.escapeHtml(row.label)}</td>` +
            window.SD_MONEY.cells(row.amount) +
            `<td class="numeric">${A.formatDecimal(row.share, 2)}%</td>` +
            `<td>${A.escapeHtml(row.anchor_product || '—')}</td>` +
            `<td class="numeric">${A.formatDecimal(row.anchor_share, 1)}%</td>`);

        const matrix = volumen.matrix || [];
        qs('#volumeMatrixCard').hidden = matrix.length === 0;
        A.fillTable('volumeMatrixTable', matrix, (row) =>
            `<td>${A.escapeHtml(row.client)}</td>` +
            `<td>${A.escapeHtml(row.product)}</td>` +
            window.SD_MONEY.cells(row.amount) +
            `<td class="numeric">${A.formatDecimal(row.client_share, 1)}%</td>` +
            `<td class="numeric">${A.formatDecimal(row.product_share, 1)}%</td>`);

        const mix = volumen.category_mix || [];
        qs('#volumeMixCard').hidden = mix.length === 0;
        A.fillTable('volumeMixTable', mix, (row) =>
            `<td>${A.escapeHtml(A.dimensionLabel(row.label))}</td>` +
            `<td class="numeric">${A.formatDecimal(row.current_share, 1)}%</td>` +
            `<td class="numeric ${A.deltaClass(row.share_change)}">` +
            `${A.formatDelta(row.share_change, ' pp')}</td>` +
            window.SD_MONEY.cells(row.current_amount));

        renderVolumeDecomposition(volumen.decomposition);
    }

    function renderAbcChart(abc) {
        A.makeChart('chartVolumeAbc', {
            type: 'doughnut',
            data: {
                labels: abc.map((row) => `Clase ${row.abc_class}`),
                datasets: [{
                    data: abc.map((row) => A.chartAmount(row.amount)),
                    backgroundColor: [A.BRAND[3], A.BRAND[2], A.BRAND[5]]
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { position: 'right' },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => {
                                const row = abc[ctx.dataIndex];
                                return `${A.formatInt(row.products)} productos · ` +
                                       `${A.formatDecimal(row.percentage, 1)}% de la venta`;
                            },
                            afterLabel: (ctx) => A.ABC_DESCRIPTIONS[abc[ctx.dataIndex].abc_class] || ''
                        }
                    }
                }
            }
        });
    }

    function renderVolumeDecomposition(decomposition) {
        const block = qs('#volumeDecompositionBlock');
        const byProduct = (decomposition && decomposition.by_product) || [];
        if (!byProduct.length) {
            block.hidden = true;
            return;
        }
        block.hidden = false;

        qs('#volumeDecompositionNote').textContent =
            `${A.formatDateMonth(decomposition.current_month)} cerró en ` +
            `${window.SD_MONEY.inline(decomposition.current_amount)} contra ` +
            `${window.SD_MONEY.inline(decomposition.previous_amount)} de ` +
            `${A.formatDateMonth(decomposition.previous_month)}: ` +
            `${window.SD_MONEY.inline(decomposition.change)} ` +
            `(${A.formatDelta(decomposition.change_percentage)}). Las dos lecturas ` +
            'de abajo explican ese mismo cambio.';

        fillEffects('volumeProductEffects', byProduct);
        fillEffects('volumeClientEffects', (decomposition.by_client) || []);
    }

    // ---------- Concentration ----------
    function renderConcentration(concentracion) {
        const block = qs('#concentrationBlock');
        const clients = (concentracion && concentracion.clients) || {};
        if (!clients.total_clients) {
            block.hidden = true;
            return;
        }
        block.hidden = false;

        A.fillKpis('concentrationKpis', [
            { label: 'Clientes', value: clients.total_clients, format: 'int' },
            {
                label: 'Peso del top 10', value: clients.top10_percentage, format: 'percent',
                hint: 'Qué parte de la venta hacen tus 10 mayores clientes'
            },
            {
                label: 'Clientes que hacen el 80%', value: clients.pareto_clients,
                format: 'int',
                hint: `El ${A.formatDecimal(clients.pareto_client_percentage, 1)}% de la cartera`
            }
        ]);

        A.setLevelReading('hhiReading', clients.hhi_level, A.CONCENTRATION_LEVELS);
    }

    // ---------- Efficiency ----------
    function renderEfficiency(eficiencia) {
        const block = qs('#efficiencyBlock');
        const kpis = (eficiencia && eficiencia.kpis) || [];
        if (!kpis.length) {
            block.hidden = true;
            return;
        }
        block.hidden = false;
        A.fillKpis('efficiencyKpis', kpis);

        A.fillTable('sellerTable', eficiencia.sellers, (row) =>
            `<td>${A.escapeHtml(row.seller)}</td>` +
            window.SD_MONEY.cells(row.amount, 2, 'hero') +
            `<td class="numeric">${A.formatInt(row.orders)}</td>` +
            `<td class="numeric">${A.formatInt(row.clients)}</td>` +
            window.SD_MONEY.cells(row.average_ticket));

        const prices = eficiencia.prices || [];
        qs('#priceCard').hidden = prices.length === 0;
        A.fillTable('priceTable', prices, (row) =>
            `<td>${A.escapeHtml(row.product)}</td>` +
            window.SD_MONEY.cells(row.previous_price) +
            window.SD_MONEY.cells(row.current_price) +
            `<td class="numeric ${A.deltaClass(row.change)}">${A.formatDelta(row.change)}</td>`);
    }

    Object.assign(A, {
        renderCommercialSummary, renderSummaryCharts
    });
})(window.SD_ANALYSIS = window.SD_ANALYSIS || {});
