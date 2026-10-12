'use strict';

/**
 * Stock del día: coverage, what is about to run out and idle capital.
 */
(function (A) {
    if (!window.SD_AUTH.isAuthenticated()) return;
    const { qs, qsAll, toast, setButtonBusy } = window.SD_UI;

    // ---------- Stock ----------
    // Engine codes, worded here.
    const STOCK_STATUS_LABELS = {
        OUT_OF_STOCK: 'Sin stock',
        CRITICAL: 'Crítico',
        LOW: 'Bajo',
        HEALTHY: 'Sano',
        EXCESS: 'Exceso',
        NO_DEMAND: 'Sin rotación'
    };

    const STOCK_UNAVAILABLE = {
        NO_SNAPSHOT: 'Todavía no cargaste una foto de inventario para este ' +
            'archivo. Súbela con el formato de la hoja Stock de la plantilla y ' +
            'este tablero se enciende.',
        NO_PRODUCTS: 'La foto de inventario no tiene productos que se puedan ' +
            'cruzar con el catálogo de ventas.'
    };

    // The order in which the situations are read: what is missing first.
    const STOCK_STATUS_ORDER = ['OUT_OF_STOCK', 'CRITICAL', 'LOW', 'HEALTHY',
        'EXCESS', 'NO_DEMAND'];

    function stockBadge(code) {
        return `<span class="badge badge-${String(code).toLowerCase()}">` +
               `${A.escapeHtml(STOCK_STATUS_LABELS[code] || code)}</span>`;
    }

    function coverageCell(row) {
        return row.coverage_days == null
            ? '<span class="cell-note">sin rotación</span>'
            : `${A.formatDecimal(row.coverage_days, 1)} d`;
    }

    /**
     * Today's stock: how long it lasts, what is about to run out and how much
     * capital sits idle. `Disponible` reflects what the ERP already committed.
     */
    function renderStock(data) {
        const empty = qs('#stockEmpty');
        const content = qs('#stockContent');

        if (!data || data.available !== true) {
            const code = data && data.reason_code;
            empty.textContent = STOCK_UNAVAILABLE[code] ||
                'No hay una foto de inventario que se pueda leer.';
            empty.hidden = false;
            content.hidden = true;
            qs('#stockSubtitle').textContent = '';
            A.showPeriodBar(data && data.period);
            A.showAnalysisView('stepStock');
            return;
        }
        empty.hidden = true;
        content.hidden = false;

        const kpis = data.kpis || {};
        qs('#stockSubtitle').textContent =
            `Foto del ${A.formatDate(kpis.snapshot_date)}. La cobertura se mide con ` +
            'la venta observada en el período, no con una proyección. Se valoriza ' +
            `en bolivianos; USD y USDT al tipo de hoy. ${window.SD_MONEY.ratesNote(data.rates)}`;

        A.fillKpis('stockKpis', [
            { label: 'Valor del inventario', value: kpis.stock_value, format: 'money3',
              hint: kpis.stock_value == null
                  ? 'Falta el costo unitario para valorizarlo'
                  : 'Existencia por su costo unitario' },
            { label: 'Capital quieto', value: kpis.excess_value, format: 'money3',
              hint: `${A.formatInt(kpis.excess_products)} productos con exceso o sin ` +
                    'rotación' },
            { label: 'Venta diaria en riesgo', value: kpis.stockout_value_at_risk,
              format: 'money3',
              hint: 'Lo que se deja de vender por día si no se repone' },
            { label: 'Productos', value: kpis.products, format: 'int',
              hint: `${A.formatDecimal(kpis.units_on_hand, 0)} unidades en almacén` },
            { label: 'Disponible', value: kpis.units_available, format: 'int',
              hint: `${A.formatDecimal(kpis.units_committed, 0)} unidades ya ` +
                    'comprometidas por el ERP' },
            { label: 'Sin stock', value: kpis.out_of_stock, format: 'int',
              hint: 'Productos en cero que sí tienen demanda' },
            { label: 'Por quebrar', value: kpis.at_risk, format: 'int',
              hint: 'Sin stock, críticos y bajos juntos' },
            { label: 'Cobertura promedio', value: kpis.average_coverage_days,
              format: 'decimal', hint: 'Días que dura el stock al ritmo actual' }
        ]);

        qs('#stockNote').textContent =
            'La columna «Disponible» es existencia menos lo que tu ERP ya tiene ' +
            'comprometido en pedidos: se lee de tu sistema, no se reserva acá.';

        renderStockCharts(data.products || []);

        A.fillTable('stockRiskTable', data.at_risk, (row) =>
            `<td>${A.escapeHtml(row.label)}</td>` +
            `<td>${row.abc_class
                ? `<span class="badge badge-${row.abc_class.toLowerCase()}">` +
                  `${row.abc_class}</span>` : '—'}</td>` +
            `<td class="numeric">${A.formatDecimal(row.on_hand, 0)}</td>` +
            `<td class="numeric">${A.formatDecimal(row.available, 0)}</td>` +
            `<td class="numeric">${A.formatDecimal(row.daily_demand, 2)}</td>` +
            `<td class="numeric">${coverageCell(row)}</td>` +
            `<td>${A.escapeHtml(A.formatDate(row.stockout_date))}</td>` +
            `<td>${stockBadge(row.status_code)}</td>`);

        A.fillTable('stockExcessTable', data.excess, (row) =>
            `<td>${A.escapeHtml(row.label)}</td>` +
            `<td>${row.abc_class
                ? `<span class="badge badge-${row.abc_class.toLowerCase()}">` +
                  `${row.abc_class}</span>` : '—'}</td>` +
            `<td class="numeric">${A.formatDecimal(row.on_hand, 0)}</td>` +
            `<td class="numeric">${coverageCell(row)}</td>` +
            `<td class="numeric">${A.formatDecimal(row.excess_units, 0)}</td>` +
            window.SD_MONEY.cells(row.excess_value) +
            `<td>${stockBadge(row.status_code)}</td>`);

        A.showPeriodBar(data.period);
        A.showAnalysisView('stepStock');
    }

    function renderStockCharts(products) {
        const counts = STOCK_STATUS_ORDER.map((code) =>
            products.filter((row) => row.status_code === code).length);
        const values = STOCK_STATUS_ORDER.map((code) => products
            .filter((row) => row.status_code === code)
            .reduce((total, row) => total + (A.chartAmount(row.stock_value) || 0), 0));
        const labels = STOCK_STATUS_ORDER.map((code) => STOCK_STATUS_LABELS[code]);
        const colours = [A.BRAND[1], A.BRAND[7], A.BRAND[4], A.BRAND[3], A.BRAND[2], A.BRAND[5]];

        A.makeChart('chartStockStatus', {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{ label: 'Productos', data: counts, backgroundColor: colours }]
            },
            options: A.chartOptions('int')
        });

        A.makeChart('chartStockValue', {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{ data: values, backgroundColor: colours }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { position: 'right' },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => `${A.chartSymbol()} ${A.formatDecimal(ctx.parsed, 2)}`
                        }
                    }
                }
            }
        });
    }

    Object.assign(A, {
        renderStock, renderStockCharts
    });
})(window.SD_ANALYSIS = window.SD_ANALYSIS || {});
