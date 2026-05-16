/**
 * MiningApiService — thin wrapper around the public mining-analysis endpoints.
 *
 * Tries `miningBaseUrl` first; on failure (network error or non-2xx) falls
 * back to `miningBaseUrlFallback`. Keeps the working base in memory so
 * subsequent calls hit it directly. JSON responses are returned parsed;
 * binary endpoints return their URL so the caller can use them in <img>
 * tags or download buttons without re-fetching.
 *
 * When the page runs on a local hostname (localhost / 127.0.0.1 / 0.0.0.0)
 * the order is inverted so dev hits the local backend first and avoids the
 * CORS noise of an unauthorized preflight to production.
 */
const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1', '0.0.0.0']);

export class MiningApiService {
    constructor({ miningBaseUrl, miningBaseUrlFallback } = {}) {
        const remote = miningBaseUrl?.replace(/\/$/, '') || '';
        const local = miningBaseUrlFallback?.replace(/\/$/, '') || '';
        const hostname = typeof window !== 'undefined'
            ? window.location.hostname
            : '';
        if (LOCAL_HOSTS.has(hostname) && local) {
            this.primary = local;
            this.fallback = remote;
        } else {
            this.primary = remote;
            this.fallback = local;
        }
        this.activeBase = null;
    }

    async _fetchJson(path, params) {
        const qs = params ? '?' + new URLSearchParams(params).toString() : '';
        const candidates = this.activeBase
            ? [this.activeBase]
            : [this.primary, this.fallback].filter(Boolean);

        let lastError = null;
        for (const base of candidates) {
            try {
                const response = await fetch(`${base}${path}${qs}`, {
                    headers: { 'Accept': 'application/json' },
                });
                if (!response.ok) {
                    lastError = new Error(`HTTP ${response.status} on ${base}${path}`);
                    continue;
                }
                this.activeBase = base;
                return await response.json();
            } catch (err) {
                lastError = err;
            }
        }
        console.error('MiningApiService: every base URL failed.', lastError);
        return null;
    }

    /** Returns the active base URL or falls back to primary when none is locked yet. */
    getActiveBase() {
        return this.activeBase || this.primary || this.fallback || '';
    }

    /** GET /public/reports/daily?date=YYYY-MM-DD */
    async getDailyReport(refDate) {
        return this._fetchJson('/public/reports/daily', { date: refDate });
    }

    /** GET /public/reports/biweekly?year=&month=&half= */
    async getBiweeklyReport(year, month, half) {
        return this._fetchJson('/public/reports/biweekly', { year, month, half });
    }

    /** GET /public/reports/biweekly/history?from=&to= */
    async getBiweeklyHistory({ from, to } = {}) {
        const params = {};
        if (from) params.from = from;
        if (to) params.to = to;
        return this._fetchJson('/public/reports/biweekly/history', params);
    }

    /** Direct binary URL for embedding or download (PNG / PDF). */
    biweeklyAssetUrl(year, month, half, format = 'png') {
        const base = this.getActiveBase();
        const qs = new URLSearchParams({ year, month, half }).toString();
        return `${base}/public/reports/biweekly/${format}?${qs}`;
    }

    dailyAssetUrl(refDate, format = 'png') {
        const base = this.getActiveBase();
        const qs = new URLSearchParams({ date: refDate }).toString();
        return `${base}/public/reports/daily/${format}?${qs}`;
    }
}
