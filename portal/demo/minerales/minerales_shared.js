'use strict';

/**
 * Cotizaciones — shared layer for the two panels of the module.
 *
 * One place for the formatters, the wording of every code the services answer,
 * and the MINING_ANALYSIS endpoints of the market side. `minerales.js` paints
 * the official quotation and the dollar; `anticipada.js` paints the quotation
 * the fortnight in progress is heading to. Both read the numbers the same way,
 * so the reader never sees the same figure written two different ways.
 */
(function () {
    const MINING_BASE = `${window.SD_CONFIG.MINING_URL}/v1/mining-analysis`;
    const API = window.SD_API;

    // Confidence and method travel as codes; the wording is ours.
    const CONFIDENCE_LABELS = {
        HIGH: 'Alta', MEDIUM: 'Media', LOW: 'Baja',
        INSUFFICIENT: 'Datos insuficientes',
        // The estimate uses NONE for a mineral with no free daily source, which
        // is not a data problem but a missing feed.
        NONE: 'Sin fuente diaria'
    };

    const METHOD_LABELS = {
        DAMPED_TREND: 'Tendencia amortiguada',
        LINEAR: 'Tendencia lineal',
        MOVING_AVERAGE: 'Promedio móvil',
        NAIVE: 'Sin cambio'
    };

    // Where a daily price came from. The names are the ones the market uses,
    // because whoever reads this screen negotiates with them.
    const SOURCE_LABELS = {
        LBMA_GOLD_AM: 'LBMA · fixing AM',
        LBMA_SILVER: 'LBMA · fixing',
        LME_CASH_WESTMETALL: 'LME cash'
    };

    // Which part of the Art. 227 scale decided the rate.
    const BASIS_LABELS = {
        FORMULA: 'fórmula',
        CAP: 'techo',
        FLOOR: 'piso',
        FIXED: 'fija'
    };

    const SERVICE_ERRORS = {
        NO_RATE_PUBLISHED: 'Todavía no hay cotizaciones del dólar guardadas.',
        SOURCE_UNAVAILABLE: 'La fuente no respondió. Se guardó lo que sí se pudo leer.',
        SOURCE_UNREADABLE: 'La página de la fuente cambió de forma y no se ' +
            'puede leer con seguridad.',
        INVALID_DATE_RANGE: 'El plazo pedido está fuera de rango.',
        EMPTY_PERIOD: 'No hay datos en ese período.',
        UNKNOWN_MINERAL: 'Ese mineral no está en el catálogo oficial.',
        MINERAL_NOT_MARKET_QUOTED: 'Ese mineral no tiene una fuente diaria ' +
            'gratuita: su cotización viene del informe quincenal.',
        RULE_NOT_FOUND: 'Ese mineral no tiene una escala de regalía cargada.',
        ROLE_NOT_ALLOWED: 'Tu rol no permite esta acción.'
    };

    function errorText(error, fallback) {
        return SERVICE_ERRORS[error && error.code] || (error && error.message) || fallback;
    }

    // ---------- formatters ----------

    /**
     * Two decimals by default, matching the published bulletin. The service
     * already rounds HALF_UP, so this only pads and groups — it never
     * re-rounds, which is where a browser and Python disagree.
     */
    function money(value, digits = 2) {
        if (value === null || value === undefined) return '—';
        return Number(value).toLocaleString('es-BO', {
            minimumFractionDigits: digits, maximumFractionDigits: digits
        });
    }

    function percent(value, digits = 2) {
        if (value === null || value === undefined) return '—';
        const sign = value > 0 ? '+' : '';
        return `${sign}${Number(value).toFixed(digits)}%`;
    }

    function changeClass(value) {
        if (value === null || value === undefined) return '';
        if (value > 0) return 'up';
        return value < 0 ? 'down' : '';
    }

    function shortDate(value) {
        if (!value) return '—';
        const [, month, day] = value.split('-');
        return `${day}/${month}`;
    }

    function escapeHtml(value) {
        return String(value === null || value === undefined ? '' : value)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
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
        const observedPoints = observed.map(point).join(' ');
        // The projected line starts at the last observed point so the two
        // segments read as one series instead of two floating lines.
        const projectedPoints = projected.length
            ? [point(observed[observed.length - 1], observed.length - 1)]
                .concat(projected.map((value, index) => point(value, observed.length + index)))
                .join(' ')
            : '';
        return `<svg class="spark" viewBox="0 0 ${width} ${height}"
                     preserveAspectRatio="none" aria-hidden="true">
            <polyline class="spark-observed" points="${observedPoints}"></polyline>
            ${projectedPoints
                ? `<polyline class="spark-projected" points="${projectedPoints}"></polyline>`
                : ''}
        </svg>`;
    }

    // ---------- market endpoints ----------

    const market = {
        estimate: (asOf) => API.get(`${MINING_BASE}/market/estimate`,
                                   asOf ? { as_of: asOf } : null),
        series: (mineralId, params) => API.get(
            `${MINING_BASE}/market/prices/${encodeURIComponent(mineralId)}`, params || null
        ),
        sync: (daysBack) => API.post(
            `${MINING_BASE}/market/sync${daysBack ? `?days_back=${daysBack}` : ''}`
        ),
        rules: () => API.get(`${MINING_BASE}/royalty-rules`)
    };

    window.SD_MIN = {
        MINING_BASE, market,
        CONFIDENCE_LABELS, METHOD_LABELS, SOURCE_LABELS, BASIS_LABELS,
        errorText, money, percent, changeClass, shortDate, escapeHtml, sparkline
    };
})();
