'use strict';

/**
 * What the five pages of the Análisis Financiero share: the calls to FINANCE,
 * the wording of every line and every code (the backend sends codes, the
 * sentences live here), the period selector and the three currencies.
 *
 * Every amount comes from FINANCE in bolivianos with the rates of its own
 * period —the official dollar and USDT at its close— so each is read in the
 * three currencies at the rate of its period, never at today's. A rate that
 * does not exist (USDT before its series began) shows as an empty cell.
 */
(function () {

    const api = window.SD_API;
    const base = () => `${window.SD_CONFIG.FINANCE_URL}/v1/finance`;

    const MONTHS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
        'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];

    // The income statement, in the order Rafael approved on 16-oct.
    const STATEMENT_LINES = [
        ['sales', 'Ventas', 'total'],
        ['sales_vat', '(−) IVA de las ventas'],
        ['transactions_tax', '(−) IT'],
        ['net_sales', 'Ventas netas', 'total'],
        ['cost_of_sales', '(−) Costo de ventas'],
        ['gross_profit', 'Utilidad bruta', 'total'],
        ['operating_expenses', '(−) Gastos de operación'],
        ['operating_profit', 'Utilidad operativa (EBIT)', 'total'],
        ['financial_result', '(±) Resultado financiero'],
        ['profit_before_income_tax', 'Utilidad antes del IUE', 'total'],
        ['income_tax_estimated', '(−) IUE estimado (25 % de la utilidad)'],
        ['net_profit_estimated', 'Utilidad neta estimada', 'total']
    ];

    const NOTICES = {
        IUE_PROVISION_NOT_SET: 'Todavía no definiste tu provisión del IUE: la sugerida es el 2 % ' +
            'de lo facturado. Defínela en Impuestos.',
        IT_NOT_LOADED: 'Hay ventas con factura y no se cargó el IT (cuenta 6.1.10).',
        NO_BALANCE: 'Este período no tiene saldos cargados: no hay balance.',
        BALANCE_MISMATCH: 'El balance no cuadra: el activo no es igual al pasivo más el patrimonio. ' +
            'Revisa los saldos cargados.',
        NOT_ENOUGH_HISTORY_FOR_TRENDS: 'Con menos de 3 meses cargados no se pueden ver tendencias.',
        NOT_ENOUGH_HISTORY_FOR_PROJECTION: 'Con menos de 12 meses cargados todavía no se puede proyectar.',
        RATES_UNAVAILABLE: 'No se pudo leer el tipo de cambio: los montos se ven sólo en bolivianos.'
    };

    const ERRORS = {
        ROLE_NOT_ALLOWED: 'Tu usuario no tiene acceso al análisis financiero.',
        EMPTY_LOAD: 'El archivo no tiene filas.',
        UNKNOWN_ACCOUNT: 'La cuenta no está en el catálogo.',
        ACCOUNT_IS_GROUP: 'Es un grupo: los montos van en sus cuentas.',
        MISSING_DATE: 'Falta la fecha.',
        INVALID_PERIODICITY: 'La periodicidad no es Diaria, Mensual ni Anual.',
        DATE_PERIODICITY_MISMATCH: 'La fecha no corresponde a la periodicidad.',
        PERIODICITY_CONFLICT: 'Ese período ya tiene montos con otra periodicidad.',
        INVALID_AMOUNT: 'El monto falta o no es un número.',
        NEGATIVE_AMOUNT: 'El monto es negativo: todo se carga en positivo.',
        FUTURE_PERIOD: 'La fecha es posterior a hoy.',
        DUPLICATE_ROW: 'Esa cuenta ya tiene un monto en ese período.',
        MISSING_TAXES_INCLUDED: 'Falta «Impuestos incluidos» (Sí o No) en una cuenta con factura.',
        ENTRY_NOT_FOUND: 'Ese monto ya no existe.',
        PARAMETER_NOT_FOUND: 'Ese parámetro no existe.',
        PARAMETERS_SERVICE_REJECTED: 'No se pudieron leer los parámetros del cálculo.',
        PARAMETER_MISSING: 'Falta un parámetro del cálculo; avisa al administrador.'
    };

    const PERIODICITY_LABELS = { DAILY: 'Diaria', MONTHLY: 'Mensual', ANNUAL: 'Anual' };
    const FLOW_LABELS = { PROCESSED: 'Procesada', BASE: 'Base' };
    const CHANNEL_LABELS = { API: 'API', FILE: 'Archivo' };

    /** The message of a failed call: its code in words, or the fallback. */
    function errorText(error, fallback) {
        const code = error && (error.code || error.message);
        return ERRORS[code] || fallback;
    }

    /** 'YYYY-MM' as «marzo de 2026»; 'YYYY' as «Año 2026». */
    function periodLabel(key) {
        if (!key) return '—';
        if (key.length === 4) return `Año ${key}`;
        const [year, month] = key.split('-');
        return `${MONTHS[Number(month) - 1]} de ${year}`;
    }

    /**
     * Bolivianos in the three currencies at the rates of their period. A
     * missing rate leaves its currency empty instead of dividing by nothing.
     */
    function money(bob, exchange) {
        const at = (rate) => (bob == null || !rate) ? null : bob / rate;
        return { bob, usd: at(exchange && exchange.usd), usdt: at(exchange && exchange.usdt) };
    }

    const get = (path, query) => api.get(`${base()}${path}`, query);

    let reportPromise = null;
    /** The report, asked once per page. */
    function report() {
        if (!reportPromise) reportPromise = get('/report');
        return reportPromise;
    }

    /**
     * Fills a <select> with every month and year of the report, newest month
     * first, and calls `onChange(period)` with the chosen one.
     */
    function periodSelect(select, data, onChange) {
        const months = [...data.months].reverse();
        const years = [...data.years].reverse();
        select.innerHTML =
            `<optgroup label="Meses">${months.map((p) =>
                `<option value="${p.period}">${periodLabel(p.period)}</option>`).join('')}</optgroup>` +
            `<optgroup label="Años">${years.map((p) =>
                `<option value="${p.period}">${periodLabel(p.period)}</option>`).join('')}</optgroup>`;
        const find = (key) => data.months.concat(data.years).find((p) => p.period === key);
        select.addEventListener('change', () => onChange(find(select.value)));
        if (months.length || years.length) onChange(find(select.value));
    }

    /** The notices of a period and of the report, in words. */
    function noticesHtml(codes) {
        const unique = [...new Set(codes || [])].filter((code) => NOTICES[code]);
        return unique.map((code) => `<li>${NOTICES[code]}</li>`).join('');
    }

    /** Where the rates of a period come from, in one line. */
    function ratesLine(exchange) {
        if (!exchange) return 'Sin tipo de cambio: montos sólo en bolivianos.';
        const fmt = (value) => value == null ? 'sin dato' : `Bs ${value.toLocaleString('es-BO', {
            minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        const [year, month, day] = exchange.date.split('-');
        return `Tipo de cambio al ${day}/${month}/${year}: dólar oficial ${fmt(exchange.usd)} · ` +
            `USDT ${fmt(exchange.usdt)}.`;
    }

    /**
     * One table row: a label and an amount in Bs, USD and USDT at the rates
     * of its period. A calculated figure says so next to it.
     */
    function moneyRow(label, line, exchange, total) {
        const amount = line == null ? null : (typeof line === 'object' ? line.amount : line);
        // A subtotal is calculated by definition; the mark is for the lines
        // whose origin could go either way —the IT, loaded or calculated.
        const origin = !total && line && typeof line === 'object' && line.origin === 'CALCULATED'
            ? ' <span class="origin-tag">calculado</span>' : '';
        return `<tr class="${total ? 'total' : ''}"><td class="line-label">${label}${origin}</td>` +
            window.SD_MONEY.cells(money(amount, exchange), 2) + '</tr>';
    }

    /**
     * Cards in rows of `columns`, the way the portal lays out its metrics:
     * one card on its own would stretch across the whole page.
     */
    function arrange(box, cards, columns = 3) {
        box.innerHTML = '';
        for (let start = 0; start < cards.length; start += columns) {
            const row = document.createElement('div');
            row.className = 'metric-row';
            row.style.setProperty('--columns', columns);
            cards.slice(start, start + columns).forEach((card) => row.appendChild(card));
            box.appendChild(row);
        }
    }

    window.SD_FINANCE = {
        arrange,
        STATEMENT_LINES, PERIODICITY_LABELS, FLOW_LABELS, CHANNEL_LABELS,
        errorText, periodLabel, money, moneyRow, report, periodSelect, noticesHtml, ratesLine,
        get,
        post: (path, body) => api.post(`${base()}${path}`, body),
        put: (path, body) => api.put(`${base()}${path}`, body),
        patch: (path, body) => api.patch(`${base()}${path}`, body),
        del: (path) => api.del(`${base()}${path}`)
    };
})();
