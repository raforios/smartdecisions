'use strict';

/**
 * The wording of every code the services answer with: the backend sends
 * codes and facts, the sentence lives here.
 */
(function (A) {
    if (!window.SD_AUTH.isAuthenticated()) return;
    const { qs, qsAll, toast, setButtonBusy } = window.SD_UI;

    // Same contract for requests the service refuses outright: the backend
    // sends the code, this catalogue owns the sentence.
    const REQUEST_ERROR_MESSAGES = {
        UNSUPPORTED_FILE_FORMAT: 'Formato no soportado. Sube un archivo .xlsx o .csv.',
        EMPTY_UPLOAD: 'El archivo que subiste está vacío.',
        FILES_SERVICE_UNREACHABLE: 'No se pudo contactar al servicio de archivos.',
        FILES_SERVICE_REJECTED_UPLOAD: 'El servicio de archivos rechazó la subida.',
        FILES_SERVICE_REJECTED: 'No se pudo leer el archivo cargado. Vuelve a intentarlo en un momento.',
        FILES_SERVICE_NOT_CONFIGURED: 'El servicio de archivos no está configurado.'
    };

    // Falls back to the raw message so services that still answer with prose
    // keep working while they migrate to codes.
    function errorText(error, fallback) {
        const code = error && error.code;
        return REQUEST_ERROR_MESSAGES[code]
            || ANALYTICS_ERRORS[code]
            || (error && error.message)
            || fallback;
    }

    // Portfolio health: the backend says WHY with a code and ships the facts
    // alongside it (dias_sin_comprar, variacion). The sentence is built here.
    const RISK_REASONS = {
        LONG_SILENCE: (row) =>
            `Sin comprar hace ${A.formatInt(row.days_without_purchase)} días. ` +
            'Campaña de reactivación.',
        SILENCE: (row) => `No compra hace ${A.formatInt(row.days_without_purchase)} días.`,
        PURCHASE_DROP: (row) =>
            `Su última compra cayó ${A.formatDecimal(Math.abs(row.change || 0), 0)}% ` +
            'frente a su promedio mensual.'
    };

    function riskReasonText(row) {
        const build = RISK_REASONS[row && row.reason_code];
        return build ? build(row) : '';
    }

    // Every headline KPI the API can report. The backend sends `metric_code`,
    // `value` and, when the number refers to a period, `reference`.
    const KPI_LABELS = {
        TOTAL_SALES: ['Venta total', 'Suma de todas las ventas del periodo'],
        SALES_COUNT: ['Número de ventas', 'Cantidad de pedidos/transacciones'],
        AVERAGE_TICKET: ['Ticket promedio', 'Venta total ÷ número de ventas'],
        UNITS_SOLD: ['Unidades vendidas', 'Suma de las cantidades vendidas'],
        CLIENT_COUNT: ['Clientes', 'Puntos de venta distintos con compras'],
        PRODUCT_COUNT: ['Productos', 'SKUs distintos vendidos'],
        UNITS_PER_ORDER: ['Unidades por pedido', 'Drop size: unidades que salen en cada pedido'],
        PRODUCTS_PER_ORDER: ['Productos por pedido',
            'Líneas distintas por pedido — mide la venta cruzada'],
        AMOUNT_PER_ORDER: ['Monto por pedido', 'Ticket promedio del período'],
        ORDER_COUNT: ['Pedidos', 'Transacciones distintas en el período'],
        MOM_CHANGE: ['Variación vs mes anterior', 'Crecimiento mes contra mes (MoM)'],
        YOY_CHANGE: ['Variación vs año anterior', null],
        LAST_MONTH_SALES: ['Venta del último mes', null],
        MONTHLY_AVERAGE: ['Promedio mensual', 'Venta media por mes del período'],
        GROSS_MARGIN: ['Margen bruto', 'Venta menos costo de la mercadería vendida'],
        GROSS_MARGIN_PERCENT: ['Margen bruto %',
            'Qué porcentaje de cada boliviano vendido queda'],
        COST_OF_GOODS: ['Costo de la mercadería', 'Lo que costó comprar lo que se vendió'],
        MARGIN_PER_ORDER: ['Margen por pedido', 'Ganancia bruta promedio de cada pedido'],
        PORTFOLIO_CLIENTS: ['Clientes en la cartera',
            'Clientes distintos que compraron en el período'],
        ACTIVE_LAST_MONTH: ['Activos el último mes', 'Compraron en el mes más reciente'],
        COVERAGE: ['Cobertura', 'Activos del último mes sobre la cartera total'],
        CHURN_LAST_MONTH: ['Churn del último mes',
            'Clientes que compraron el mes previo y dejaron de comprar'],
        CLIENTS_AT_RISK: ['Clientes en riesgo',
            'Cayeron fuerte o llevan 2 meses sin comprar — visitarlos ahora'],
        CLIENTS_LOST: ['Clientes perdidos', 'Más de 6 meses sin comprar — campaña de reactivación'],
        PURCHASE_FREQUENCY: ['Frecuencia de compra', 'Pedidos por cliente por mes']
    };

    // A few KPIs read better with the period the number belongs to.
    /**
     * Label of a KPI card.
     *
     * Cards from the backend carry `metric_code` and are translated here. Cards
     * the frontend builds —concentration, volume source— carry their label
     * written in: without this fallback they reached the screen untitled.
     */
    function kpiLabel(card) {
        const entry = KPI_LABELS[card && card.metric_code];
        if (!entry) {
            if (card && card.label) return card.label;
            return card && card.metric_code ? String(card.metric_code) : '';
        }
        if (card.metric_code === 'LAST_MONTH_SALES' && card.reference) {
            return `Venta de ${card.reference}`;
        }
        return entry[0];
    }

    // Codes the analytics engines report, worded here.
    const MARGIN_ALERT_REASONS = {
        BELOW_COST: 'Se vende por debajo del costo',
        THIN_MARGIN: 'Margen casi nulo'
    };

    const ABC_DESCRIPTIONS = {
        A: 'Núcleo del negocio: concentran el 80% de la venta. Nunca deben quebrar stock.',
        B: 'Complementarios: aportan el siguiente 15%. Mantener con rotación controlada.',
        C: 'Cola larga: el 5% restante. Candidatos a depurar o vender bajo pedido.'
    };

    const FORECAST_METHODS = {
        linear: 'Tendencia lineal',
        moving_average: 'Media móvil'
    };

    function otherMethod(method) {
        return method === 'moving_average' ? 'linear' : 'moving_average';
    }

    const ANALYTICS_ERRORS = {
        INVALID_DATE: 'La fecha no es válida. Usa el formato AAAA-MM-DD.',
        NO_DATE_COLUMN: 'El archivo no tiene una columna de fecha válida, ' +
            'no se puede filtrar por período.',
        EMPTY_PERIOD: 'No hay ventas en el período seleccionado. Elige otro rango.',
        DATASET_UNREADABLE: 'No se pudo leer el archivo cargado. Vuelve a intentarlo en un momento.',
        DATASET_NOT_FOUND: 'No encontramos tus datos de ventas. Cárgalos en Cargar datos.',
        DATASET_NOT_VALIDATED: 'Tu archivo de ventas no pasó la validación. Corrígelo y vuelve a cargarlo.',
        UNSUPPORTED_FILE_TYPE: 'El archivo debe ser Excel (.xlsx) o CSV.',
        FORECAST_UNAVAILABLE: 'No se pudo calcular el pronóstico en este momento. Vuelve a intentarlo.'
    };

    // The same level code, read over products instead of clients: the
    // sentence changes because depending on a SKU is not managed like
    // depending on an account.
    const VOLUME_LEVELS = {
        HIGH: 'Alta: el volumen depende de muy pocos productos.',
        MODERATE: 'Moderada: hay dependencia de algunos productos clave.',
        LOW: 'Baja: el volumen está bien repartido en el catálogo.'
    };

    const CONCENTRATION_LEVELS = {
        HIGH: 'Alta: la venta depende de muy pocos clientes.',
        MODERATE: 'Moderada: hay dependencia de algunos clientes clave.',
        LOW: 'Baja: la venta está bien repartida entre los clientes.'
    };

    // The reading is a traffic light: the text takes the colour of its level
    // so "Alta" is red before it is read, and "Baja" is green.
    function setLevelReading(elementId, level, texts) {
        const node = qs('#' + elementId);
        node.textContent = texts[level] || '';
        node.classList.remove('level-low', 'level-moderate', 'level-high');
        if (texts[level]) node.classList.add(`level-${String(level).toLowerCase()}`);
    }

    // A dimension the source file left blank still needs a row label.
    function dimensionLabel(value) {
        return value ? String(value) : 'Sin especificar';
    }

    function kpiHint(card) {
        const entry = KPI_LABELS[card && card.metric_code];
        if (card && card.metric_code === 'YOY_CHANGE') {
            return card.reference
                ? `Mismo mes de ${String(card.reference).slice(0, 4)} (YoY)`
                : 'Se necesita un año de historial';
        }
        // Same as the label: a hand-built card's note is the one the card
        // carries.
        return entry ? entry[1] : ((card && card.hint) || null);
    }

    Object.assign(A, {
        ABC_DESCRIPTIONS, CONCENTRATION_LEVELS, FORECAST_METHODS, MARGIN_ALERT_REASONS,
        VOLUME_LEVELS, dimensionLabel, errorText, kpiHint, kpiLabel, otherMethod,
        riskReasonText, setLevelReading
    });
})(window.SD_ANALYSIS = window.SD_ANALYSIS || {});
