'use strict';

/**
 * The recent activity of the platform, for the ADMIN: calls answered and
 * failed per hour, the latest failures and the latest audited changes, read
 * from EVENTS (`/v1/events/activity`, ADMIN only). Used by Administración ›
 * Eventos and by the segment on Principal. Also "Lo último que hiciste" on
 * the Principal of the other roles: each user's own audited changes
 * (`/v1/events/my-changes`, the user is the one in the token).
 *
 * EVENTS records every product, its clients' included; the dashboard names
 * the services it covers: ours that report to it. AUTH, FILES and
 * ML_FUNCTIONS do not report, by design.
 */
(function platformEventsModule() {
    const REPORTING = ['AI', 'COMMERCIAL', 'MINING_ANALYSIS', 'QUOTES', 'FINANCE', 'BILLING'];
    // The names COMMERCIAL had before 23-oct-2026: a user's own history keeps
    // what was recorded under them.
    const RECORDED_BEFORE = ['INGEST', 'ANALYTICS', 'OPTIMIZATION'];

    // What the services audit, in words; any other action is shown as it is.
    const ACTIONS = { CREATE: 'Alta', UPDATE: 'Cambio', DELETE: 'Baja', UPLOAD: 'Carga',
        RUN: 'Cálculo', ACTIVATE: 'Activación', DEACTIVATE: 'Desactivación', UPSERT: 'Cambio',
        UPLOAD_S3: 'Carga', LOAD: 'Carga', BULK_CREATE: 'Alta masiva', SYNC: 'Actualización',
        GENERATE: 'Pedido', READ: 'Consulta', CLOSE: 'Cierre', REOPEN: 'Reapertura',
        INFER: 'Inferencia', REPEAT: 'Repetición', UPDATE_STATUS: 'Cambio de estado',
        ISSUE: 'Emisión', CANCEL: 'Anulación' };
    const actionLabel = (code) => ACTIONS[code] || code || '—';

    // What each audited entity is, in words, and the screen it lives on (none
    // when no screen shows it). An entity not listed is shown by its code.
    const ENTITIES = {
        'FINANCE.Account': ['Cuenta del catálogo', 'financiero/cuentas.html'],
        'FINANCE.Load': ['Carga de estados financieros', 'financiero/cargar.html'],
        'FINANCE.Entry': ['Monto de una cuenta', 'financiero/cargar.html'],
        'FINANCE.Period': ['Período cargado', 'financiero/cargar.html'],
        'FINANCE.BusinessModel': ['Modelo de negocio', 'financiero/modelo.html'],
        'FINANCE.ClientParameter': ['Parámetro de impuestos', 'financiero/impuestos.html'],
        'AI.Explanation': ['Explicación de la IA', null],
        'AI.Role': ['Prompt de la IA', 'admin/prompts.html'],
        'QUOTES.Factor': ['Factor externo', 'parametros/factores.html'],
        'QUOTES.ExchangeRate': ['Tipo de cambio', 'admin/tipo-cambio.html'],
        'ANALYTICS.CommercialPolicy': ['Política comercial', 'parametros/index.html'],
        'ANALYTICS.CreditPolicy': ['Política de crédito', 'parametros/index.html'],
        'ANALYTICS.AnalyticsRun': ['Análisis comercial', 'comercial/index.html'],
        'INGEST.Dataset': ['Carga de ventas', 'ventas/cargar.html'],
        'INGEST.Stock': ['Carga de inventario', 'inventario/cargar.html'],
        'INGEST.Purchases': ['Carga de compras', 'compras/cargar.html'],
        'INGEST.Collections': ['Carga de cobranza', 'cobranza/cargar.html'],
        'INGEST.Objectives': ['Carga de objetivos', 'ventas/objetivos.html'],
        'INGEST.Client': ['Cliente', 'clientes/index.html'],
        'COMMERCIAL.CommercialPolicy': ['Política comercial', 'parametros/index.html'],
        'COMMERCIAL.CreditPolicy': ['Política de crédito', 'parametros/index.html'],
        'COMMERCIAL.AnalyticsRun': ['Análisis comercial', 'comercial/index.html'],
        'COMMERCIAL.Dataset': ['Carga de ventas', 'ventas/cargar.html'],
        'COMMERCIAL.Stock': ['Carga de inventario', 'inventario/cargar.html'],
        'COMMERCIAL.Purchases': ['Carga de compras', 'compras/cargar.html'],
        'COMMERCIAL.Collections': ['Carga de cobranza', 'cobranza/cargar.html'],
        'COMMERCIAL.Objectives': ['Carga de objetivos', 'ventas/objetivos.html'],
        'COMMERCIAL.Client': ['Cliente', 'clientes/index.html']
    };
    const entity = (change) => ENTITIES[`${change.microservice}.${change.entity_name}`]
        || [change.entity_name || change.microservice, null];

    /** The activity of the last `hours` hours. */
    function load(hours) {
        return window.SD_API.get(`${window.SD_CONFIG.API_URL}/v1/events/activity`,
            { microservices: REPORTING.join(','), hours });
    }

    /** The caller's own latest changes in our services, newest first. */
    function mine(days, limit) {
        return window.SD_API.get(`${window.SD_CONFIG.API_URL}/v1/events/my-changes`,
            { microservices: REPORTING.concat(RECORDED_BEFORE).join(','), days, limit });
    }

    /** Totals over every service. */
    function totals(activity) {
        const services = activity.services || [];
        const sum = (field) => services.reduce((total, item) => total + item[field], 0);
        return {
            calls: sum('total'),
            ok: sum('ok'),
            clientErrors: sum('client_errors'),
            serverErrors: sum('server_errors'),
            failing: services.filter((item) => item.client_errors + item.server_errors > 0).length
        };
    }

    /** The hourly buckets of every service added up, oldest first. */
    function hourly(activity) {
        const byHour = new Map();
        (activity.services || []).forEach((item) => item.buckets.forEach((bucket) => {
            const slot = byHour.get(bucket.hour) || { ok: 0, errors: 0 };
            slot.ok += bucket.ok;
            slot.errors += bucket.errors;
            byHour.set(bucket.hour, slot);
        }));
        return [...byHour.entries()].map(([hour, slot]) => ({ hour, ...slot }));
    }

    /** "14:05", or "20 oct 14:05" when it was not today. */
    function when(stamp) {
        const moment = new Date(stamp);
        const time = moment.toLocaleTimeString('es-BO', { hour: '2-digit', minute: '2-digit' });
        if (moment.toDateString() === new Date().toDateString()) return time;
        return `${moment.toLocaleDateString('es-BO', { day: 'numeric', month: 'short' })} ${time}`;
    }

    /** A stacked bar chart: answered in green, failed in red, per hour. */
    function chart(canvas, activity, previous) {
        if (previous) previous.destroy();
        const color = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
        const rows = hourly(activity);
        return new window.Chart(canvas, {
            type: 'bar',
            data: {
                labels: rows.map((row) => `${row.hour.slice(11, 13)} h`),
                datasets: [
                    { label: 'Respondidas', data: rows.map((row) => row.ok),
                      backgroundColor: color('--success'), stack: 'calls' },
                    { label: 'Con error', data: rows.map((row) => row.errors),
                      backgroundColor: color('--danger'), stack: 'calls' }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: 'bottom' } },
                scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true,
                    ticks: { precision: 0 } } }
            }
        });
    }

    window.SD_EVENTS = { REPORTING, load, mine, totals, hourly, when, chart, actionLabel, entity };
})();
