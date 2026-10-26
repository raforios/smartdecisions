'use strict';

/**
 * The health of the platform, for the ADMIN: whether each of the eleven
 * services answers, how long it takes, and the state of its tables.
 *
 * `/health` is public and says only "available"; `/health/tables` is the
 * ADMIN-only route each service with tables answers (Rafael, 21-oct-2026:
 * the table names stay off the public check). FILES and ML_FUNCTIONS keep no
 * tables. Used by Administración › Salud and by the card on Principal.
 */
(function platformHealthModule() {
    // The gateway sends /v1/<path>/... to each service's Lambda.
    const SERVICES = [
        { code: 'auth', label: 'AUTH', path: 'auth', base: true },
        { code: 'events', label: 'EVENTS', path: 'events', base: true },
        { code: 'files', label: 'FILES', path: 's3', base: true, noTables: true },
        { code: 'ml_functions', label: 'ML_FUNCTIONS', path: 'common', base: true, noTables: true },
        { code: 'ai', label: 'AI', path: 'ai', base: true },
        // INGEST, ANALYTICS and OPTIMIZATION, joined on 23-oct-2026.
        { code: 'commercial', label: 'COMMERCIAL', path: 'commercial' },
        { code: 'mining_analysis', label: 'MINING_ANALYSIS', path: 'mining-analysis' },
        { code: 'quotes', label: 'QUOTES', path: 'quotes' },
        { code: 'finance', label: 'FINANCE', path: 'finance' },
        { code: 'billing', label: 'BILLING', path: 'billing' }
    ];

    // DynamoDB's own table states, in words.
    const TABLE_STATES = {
        ACTIVE: 'Activa', CREATING: 'Creándose', UPDATING: 'Actualizándose',
        DELETING: 'Borrándose', ARCHIVING: 'Archivándose', ARCHIVED: 'Archivada',
        INACCESSIBLE_ENCRYPTION_CREDENTIALS: 'Sin acceso a su cifrado',
        MISSING: 'No existe', UNREACHABLE: 'No se pudo leer'
    };
    const stateLabel = (code) => TABLE_STATES[code] || code;

    /** Whether the service answers its public health check, and how fast. */
    async function ping(service) {
        const started = performance.now();
        try {
            const response = await fetch(`${window.SD_CONFIG.API_URL}/v1/${service.path}/health`,
                { cache: 'no-store' });
            const body = response.ok ? await response.json() : null;
            return { up: Boolean(body && body.Status === 'available'),
                     ms: Math.round(performance.now() - started) };
        } catch (error) {
            return { up: false, ms: null };
        }
    }

    /** The service's tables; null when it has none or cannot say yet. */
    async function tables(service) {
        if (service.noTables) return { tables: null, tablesError: null };
        try {
            const answer = await window.SD_API.get(
                `${window.SD_CONFIG.API_URL}/v1/${service.path}/health/tables`);
            return { tables: answer, tablesError: null };
        } catch (error) {
            // 404: the service has not been deployed with the route yet.
            return { tables: null, tablesError: error.status === 404 ? 'NOT_DEPLOYED' : 'UNREADABLE' };
        }
    }

    /** Every service, checked at once. */
    async function check() {
        return Promise.all(SERVICES.map(async (service) => {
            const [health, detail] = await Promise.all([ping(service), tables(service)]);
            return { ...service, ...health, ...detail };
        }));
    }

    /** Totals for a summary: services up, and active tables of those reported. */
    function summarize(results) {
        const reported = results.filter((item) => item.tables);
        const allTables = reported.flatMap((item) => item.tables.tables);
        return {
            services: results.length,
            up: results.filter((item) => item.up).length,
            tables: allTables.length,
            activeTables: allTables.filter((table) => table.status === 'ACTIVE').length,
            notReported: results.filter((item) => !item.noTables && !item.tables).length
        };
    }

    /** The tables line of a summary, in words. */
    function tablesLine(totals) {
        if (!totals.tables) return `Ningún servicio informó sus tablas (${totals.notReported} sin informar).`;
        return `${totals.activeTables} de ${totals.tables} tablas activas` +
            (totals.notReported ? `; ${totals.notReported} servicios sin informar sus tablas` : '');
    }

    window.SD_HEALTH = { SERVICES, check, summarize, stateLabel, tablesLine };
})();
