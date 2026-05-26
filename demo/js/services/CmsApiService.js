/**
 * CmsApiService — thin wrapper around the public CMS endpoints
 * (/v1/cms/public/{news,documents,slides,entities}).
 *
 * Follows the same primary/fallback strategy as MiningApiService: tries
 * `cmsBaseUrl` first, falls back to `cmsBaseUrlFallback` on failure, and
 * caches the working base for subsequent calls. When the page runs on
 * a local hostname the order is inverted so dev hits the local backend
 * first and avoids the CORS noise of an unauthorized preflight to
 * production.
 */
const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1', '0.0.0.0']);

export class CmsApiService {
    constructor({ cmsBaseUrl, cmsBaseUrlFallback } = {}) {
        const remote = cmsBaseUrl?.replace(/\/$/, '') || '';
        const local = cmsBaseUrlFallback?.replace(/\/$/, '') || '';
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
        const filtered = Object.fromEntries(
            Object.entries(params || {}).filter(([, v]) => v != null && v !== ''),
        );
        const qs = Object.keys(filtered).length
            ? '?' + new URLSearchParams(filtered).toString()
            : '';
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
        console.error('CmsApiService: every base URL failed.', lastError);
        return null;
    }

    /** GET /public/news?lang=&type=&limit= */
    async getNews({ lang = 'es', type, limit } = {}) {
        return this._fetchJson('/public/news', { lang, type, limit });
    }

    /** GET /public/documents?lang=&type=&limit= */
    async getDocuments({ lang = 'es', type, limit } = {}) {
        return this._fetchJson('/public/documents', { lang, type, limit });
    }

    /** GET /public/slides?lang=&limit= */
    async getSlides({ lang = 'es', limit } = {}) {
        return this._fetchJson('/public/slides', { lang, limit });
    }

    /** GET /public/entities?limit= */
    async getEntities({ limit } = {}) {
        return this._fetchJson('/public/entities', { limit });
    }

    /** GET /public/news/{id} */
    async getNewsById(id) {
        return this._fetchJson(`/public/news/${encodeURIComponent(id)}`);
    }

    /** GET /public/documents/{id} */
    async getDocumentById(id) {
        return this._fetchJson(`/public/documents/${encodeURIComponent(id)}`);
    }

    /** GET /public/slides/{id} */
    async getSlideById(id) {
        return this._fetchJson(`/public/slides/${encodeURIComponent(id)}`);
    }

    /** GET /public/entities/{id} */
    async getEntityById(id) {
        return this._fetchJson(`/public/entities/${encodeURIComponent(id)}`);
    }
}
