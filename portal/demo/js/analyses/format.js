'use strict';

/**
 * Formatters, tables, metric cards and charts shared by every analysis view.
 */
(function (A) {
    if (!window.SD_AUTH.isAuthenticated()) return;
    const { qs, qsAll, toast, setButtonBusy } = window.SD_UI;

    // Amounts that come in the three currencies are shown side by side; the
    // only choice left is which one a chart draws, next to that chart.
    const CHART_CURRENCY_KEY = 'sd_chart_currency';
    const CHART_SYMBOLS = { BOB: 'Bs', USD: 'USD', USDT: 'USDT' };
    A.chartCurrency = sessionStorage.getItem(CHART_CURRENCY_KEY) || 'BOB';

    /** A Money {bob, usd, usdt} in the currency the charts draw; a number as is. */
    function chartAmount(value) {
        return window.SD_MONEY.pick(value, A.chartCurrency);
    }

    function chartSymbol() {
        return CHART_SYMBOLS[A.chartCurrency] || CHART_SYMBOLS.BOB;
    }

    function formatBytes(bytes) {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${formatDecimal(bytes / 1024, 1)} KB`;
        return `${formatDecimal(bytes / (1024 * 1024), 1)} MB`;
    }

    // ---------- Commercial summary (dashboard) ----------
    const BRAND = ['#0d1e4c', '#7a4a2a', '#c4a378', '#2d7d46', '#b8860b',
        '#5e6580', '#8a5a3a', '#3a5a8a', '#6a8a4a', '#a07040'];
    const chartRegistry = {};

    // A KPI without a value is not zero: a percentage variation with no base
    // period is undefined, and rendering it as 0% would state something false.
    function formatKpi(card) {
        if (card.value == null || isNaN(card.value)) return '—';
        if (card.format === 'money') return formatCurrency(card.value);
        if (card.format === 'percent') return `${formatDecimal(card.value, 1)}%`;
        if (card.format === 'decimal') return formatDecimal(card.value, 2);
        return formatInt(card.value);
    }

    // es-BO writes 22,2 — not 22.2. Mixing separators inside the same dashboard
    // ("Bs 254.641,43" next to "22.2%") reads as a bug to a Bolivian user.
    function formatDecimal(value, decimals) {
        return Number(value).toLocaleString('es-BO', {
            minimumFractionDigits: decimals, maximumFractionDigits: decimals
        });
    }

    /** Signed percentage with its direction, for variation cells. */
    function formatDelta(value, suffix = '%') {
        if (value == null || isNaN(value)) return '—';
        const number = Number(value);
        const sign = number > 0 ? '+' : '';
        return `${sign}${formatDecimal(number, 1)}${suffix}`;
    }

    function deltaClass(value) {
        if (value == null || isNaN(value)) return '';
        return Number(value) >= 0 ? 'delta-up' : 'delta-down';
    }

    /** Fills a table body from rows, building each cell from `cells(row)`. */
    // Every table shows ten rows and pages the rest. Ten fits on screen
    // without scrolling, which is what lets rows be compared at a glance; a
    // table that dumps sixty rows pushes the next section off the page and
    // leaves a different amount of blank space under each block.
    const TABLE_PAGE_SIZE = 10;

    function fillTable(tableId, rows, cells, options = {}) {
        const all = rows || [];
        const pages = Math.max(1, Math.ceil(all.length / TABLE_PAGE_SIZE));
        const page = Math.min(Math.max(options.page || 0, 0), pages - 1);
        const start = page * TABLE_PAGE_SIZE;
        const pageRows = all.slice(start, start + TABLE_PAGE_SIZE);

        const table = qs(`#${tableId}`);
        const tbody = table.querySelector('tbody');
        tbody.innerHTML = '';
        if (pageRows.length === 0 && options.emptyText) {
            const columns = table.querySelectorAll('thead th').length || 1;
            tbody.innerHTML = `<tr class="empty-row"><td colspan="${columns}">` +
                `${escapeHtml(options.emptyText)}</td></tr>`;
        }
        pageRows.forEach((row, index) => {
            const tr = document.createElement('tr');
            tr.innerHTML = cells(row, start + index);
            tbody.appendChild(tr);
        });
        renderPager(table, all.length, page, pages, (next) =>
            fillTable(tableId, rows, cells, { ...options, page: next }));
    }

    // The pager lives right after the table's scroll wrapper and only exists
    // while there is more than one page: a table of six rows shows no controls.
    function renderPager(table, total, page, pages, goTo) {
        const anchor = table.closest('.table-wrapper') || table;
        let pager = anchor.nextElementSibling;
        if (!pager || !pager.classList.contains('table-pager')) {
            pager = document.createElement('div');
            pager.className = 'pager table-pager';
            anchor.insertAdjacentElement('afterend', pager);
        }
        pager.hidden = pages <= 1;
        if (pages <= 1) {
            pager.innerHTML = '';
            return;
        }
        const first = page * TABLE_PAGE_SIZE + 1;
        const last = Math.min(total, (page + 1) * TABLE_PAGE_SIZE);
        pager.innerHTML =
            `<button type="button" class="btn btn-ghost btn-small" data-pager="prev"` +
            `${page === 0 ? ' disabled' : ''}>‹ Anterior</button>` +
            `<span class="pager-info">${formatInt(first)}–${formatInt(last)} de ` +
            `${formatInt(total)} · página ${page + 1} de ${pages}</span>` +
            `<button type="button" class="btn btn-ghost btn-small" data-pager="next"` +
            `${page >= pages - 1 ? ' disabled' : ''}>Siguiente ›</button>`;
        pager.querySelector('[data-pager="prev"]').addEventListener('click', () => goTo(page - 1));
        pager.querySelector('[data-pager="next"]').addEventListener('click', () => goTo(page + 1));
    }

    /** A card whose amount came as {bob, usd, usdt}. */
    function isMoney3(card) {
        return card.format === 'money3' ||
            (card.format === 'money' && card.value != null && typeof card.value === 'object');
    }

    // Today's rates while a chosen month's summary is drawn: each money card
    // then shows, under its close, the same bolivianos at today's rate.
    A.monthTodayRates = null;

    function fillKpis(containerId, cards, variantFor) {
        const box = qs('#' + containerId);
        box.innerHTML = '';
        (cards || []).forEach((card) => box.appendChild(metricCard({
            label: A.kpiLabel(card),
            value: formatKpi(card),
            // Money travels as {bob, usd, usdt}: the three side by side.
            valueHtml: isMoney3(card) ? window.SD_MONEY.card(card.value, A.monthTodayRates) : '',
            hint: A.kpiHint(card),
            variant: variantFor ? variantFor(card) : ''
        })));
        arrangeMetrics(box);
    }

    // The canvas box is fixed by CSS, so the chart has to fill it as it is.
    // With the default aspect ratio Chart.js drew a 2:1 bitmap from the width
    // and the browser stretched it to the box height: in a narrow column the
    // text came out tall and heavy, out of proportion with the bars.
    function makeChart(canvasId, config) {
        if (!window.Chart) return;
        window.Chart.defaults.maintainAspectRatio = false;
        // Axis and tooltip numbers in the Bolivian format, like every figure.
        window.Chart.defaults.locale = 'es-BO';
        if (chartRegistry[canvasId]) chartRegistry[canvasId].destroy();
        chartRegistry[canvasId] = new window.Chart(qs('#' + canvasId), config);
    }

    // Real product and client names run long — "Chocolate Barra Rellena 90g" —
    // and Chart.js keeps the axis font at its default, so on a narrow screen the
    // labels overlap into an unreadable stack. Smaller type, a cap on length and
    // a fixed axis width keep every name legible; the tooltip still shows the
    // full one.
    const AXIS_LABEL_MAX = 26;

    function shortLabel(text) {
        const clean = A.dimensionLabel(text);
        return clean.length > AXIS_LABEL_MAX
            ? `${clean.slice(0, AXIS_LABEL_MAX - 1)}…`
            : clean;
    }

    function horizontalBar(canvasId, rows, label, valueKey = 'amount') {
        const items = rows || [];
        const base = chartOptions('chartMoney');
        makeChart(canvasId, {
            type: 'bar',
            data: {
                labels: items.map((r) => shortLabel(r.label)),
                datasets: [{ label, data: items.map((r) => chartAmount(r[valueKey])),
                    backgroundColor: BRAND[1] }]
            },
            options: {
                ...base,
                indexAxis: 'y',
                maintainAspectRatio: false,
                layout: { padding: { right: 12 } },
                scales: {
                    y: {
                        ticks: {
                            font: { size: 11 },
                            autoSkip: false,
                            crossAlign: 'far'
                        },
                        grid: { display: false },
                        afterFit: (scale) => { scale.width = 148; }
                    },
                    x: {
                        ticks: { font: { size: 11 }, callback: (v) => formatCompact(v) },
                        grid: { color: 'rgba(21,36,65,.06)' }
                    }
                },
                plugins: {
                    ...base.plugins,
                    tooltip: {
                        ...base.plugins.tooltip,
                        callbacks: {
                            ...base.plugins.tooltip.callbacks,
                            // The axis may be truncated; the tooltip never is.
                            title: (ctx) => A.dimensionLabel(items[ctx[0].dataIndex].label)
                        }
                    }
                }
            }
        });
    }

    // Axis ticks in full bolivianos crowd each other; 12.500 reads as 12,5 k.
    function formatCompact(value) {
        const number = Number(value) || 0;
        if (Math.abs(number) >= 1000000) return `${formatDecimal(number / 1000000, 1)} M`;
        if (Math.abs(number) >= 1000) return `${Math.round(number / 1000)} k`;
        return number.toLocaleString('es-BO');
    }

    function chartOptions(format) {
        return {
            responsive: true,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => {
                            const value = ctx.parsed.y ?? ctx.parsed.x ?? ctx.parsed;
                            if (format === 'money') return formatCurrency(value);
                            if (format === 'chartMoney') {
                                return `${chartSymbol()} ${formatDecimal(value, 2)}`;
                            }
                            if (format === 'percent') return formatDelta(value);
                            if (format === 'int') return formatInt(value);
                            return String(value);
                        }
                    }
                }
            }
        };
    }

    // ---------- helpers ----------
    /**
     * Lays the cards of a metric grid out in symmetric rows: money cards first
     * and plain cards after, in rows of their own, at most MAX_PER_ROW per row, spread
     * as evenly as possible, every card the same width and the short rows
     * centred, so an odd count reads as a pyramid instead of a stray card.
     */
    const MAX_PER_ROW = { money: 4, plain: 6 };
    function arrangeMetrics(box) {
        const all = Array.from(box.children);
        const groups = [
            { kind: 'money', cards: all.filter((card) => card.querySelector('.money3')) },
            { kind: 'plain', cards: all.filter((card) => !card.querySelector('.money3')) }
        ].filter((group) => group.cards.length);
        box.innerHTML = '';
        groups.forEach(({ kind, cards }) => {
            const rows = Math.ceil(cards.length / MAX_PER_ROW[kind]);
            const columns = Math.ceil(cards.length / rows);
            for (let start = 0; start < cards.length; start += columns) {
                const row = document.createElement('div');
                row.className = 'metric-row';
                row.style.setProperty('--columns', columns);
                cards.slice(start, start + columns).forEach((card) => row.appendChild(card));
                box.appendChild(row);
            }
        });
    }

    function metricCard({ label, value, valueHtml, variant, hint }) {
        const node = document.createElement('div');
        node.className = 'metric';
        node.innerHTML = `
            <p class="metric-label">${escapeHtml(label)}</p>
            ${valueHtml || `<p class="metric-value ${variant || ''}">${escapeHtml(String(value))}</p>`}
            ${hint ? `<p class="metric-hint">${escapeHtml(hint)}</p>` : ''}
        `;
        return node;
    }

    // Every count shown to the user goes through here: raw String(n) leaves
    // figures like 120837 unreadable on the KPI cards.
    function formatInt(value) {
        if (value == null || isNaN(value)) return '—';
        return Number(value).toLocaleString('es-BO', { maximumFractionDigits: 0 });
    }

    function formatPercent(value) {
        if (value == null || isNaN(value)) return '—';
        return `${formatDecimal(Number(value) * 100, 1)}%`;
    }

    function formatCurrency(value) {
        // An amount in the three currencies reads as one line wherever text,
        // not a table, carries it.
        if (value != null && typeof value === 'object') return window.SD_MONEY.inline(value);
        if (value == null || isNaN(value)) return '—';
        return `Bs ${Number(value).toLocaleString('es-BO', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        })}`;
    }

    const MONTH_NAMES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
        'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];

    /**
     * 'YYYY-MM' written the way a person says it. Built from the month names
     * and not with `new Date('2026-03')`, which west of Greenwich returns the
     * previous month.
     */
    function formatDateMonth(key) {
        if (!key) return '—';
        const [year, month] = String(key).split('-');
        const name = MONTH_NAMES[Number(month) - 1];
        return name ? `${name} de ${year}` : String(key);
    }

    /**
     * 'YYYY-MM-DD' to dd/mm/yyyy, splitting the text and not with `new Date`,
     * which west of Greenwich returns the previous day.
     */
    function formatDate(value) {
        if (!value) return '—';
        const [year, month, day] = String(value).split('-');
        return day ? `${day}/${month}/${year}` : String(value);
    }

    function formatDateRange(start, end) {
        if (!start && !end) return '—';
        return `${start || '?'} → ${end || '?'}`;
    }

    function escapeHtml(value) {
        return String(value)
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#039;');
    }

    Object.assign(A, {
        BRAND, CHART_CURRENCY_KEY, CHART_SYMBOLS, arrangeMetrics, chartAmount,
        chartOptions, chartRegistry, chartSymbol, deltaClass, escapeHtml, fillKpis,
        fillTable, formatBytes, formatCurrency, formatDate, formatDateMonth,
        formatDateRange, formatDecimal, formatDelta, formatInt, formatPercent,
        horizontalBar, makeChart, metricCard, shortLabel
    });
})(window.SD_ANALYSIS = window.SD_ANALYSIS || {});
