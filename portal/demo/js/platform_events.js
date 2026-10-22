'use strict';

/**
 * The recent activity of the platform, for the ADMIN: calls answered and
 * failed per hour, the latest failures and the latest audited changes, read
 * from EVENTS (`/v1/events/activity`, ADMIN only). Used by Administración ›
 * Eventos and by the segment on Principal.
 *
 * EVENTS records every product, its clients' included; the dashboard names
 * the services it covers: ours that report to it. AUTH, FILES and
 * ML_FUNCTIONS do not report, by design.
 */
(function platformEventsModule() {
    const REPORTING = ['PARAMETERS', 'AI', 'INGEST', 'ANALYTICS', 'OPTIMIZATION',
        'MINING_ANALYSIS', 'QUOTES', 'FINANCE', 'BILLING'];

    // What the services audit, in words; any other action is shown as it is.
    const ACTIONS = { CREATE: 'Alta', UPDATE: 'Cambio', DELETE: 'Baja', UPLOAD: 'Carga',
        RUN: 'Cálculo', ACTIVATE: 'Activación', DEACTIVATE: 'Desactivación' };
    const actionLabel = (code) => ACTIONS[code] || code || '—';

    /** The activity of the last `hours` hours. */
    function load(hours) {
        return window.SD_API.get(`${window.SD_CONFIG.API_URL}/v1/events/activity`,
            { microservices: REPORTING.join(','), hours });
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

    window.SD_EVENTS = { REPORTING, load, totals, hourly, when, chart, actionLabel };
})();
