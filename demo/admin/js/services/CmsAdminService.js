/**
 * CmsAdminService — wraps the 20 JWT-protected admin endpoints exposed
 * by the CMS microservice under /v1/cms/admin.
 *
 * Every method automatically attaches the Bearer token from localStorage
 * and throws on non-2xx responses with the server's `detail` payload so
 * callers can surface meaningful errors. A 401 also clears the token to
 * force re-login.
 */
import { resolveBases, request, authHeader } from './apiClient.js';

export class CmsAdminService {
    constructor({ cmsBaseUrl, cmsBaseUrlFallback } = {}) {
        this.bases = resolveBases({
            remote: cmsBaseUrl, local: cmsBaseUrlFallback,
        });
    }

    async _send(method, path, body) {
        const init = {
            method,
            headers: { Accept: 'application/json', ...authHeader() },
        };
        if (body !== undefined) {
            init.headers['Content-Type'] = 'application/json';
            init.body = JSON.stringify(body);
        }
        const response = await request(this.bases, `/admin${path}`, init);
        if (response.status === 401) {
            localStorage.removeItem('admin_jwt');
            throw new Error('Sesión expirada — vuelve a iniciar sesión.');
        }
        if (!response.ok) {
            const payload = await response.json().catch(() => null);
            throw new Error(_formatError(payload, response.status));
        }
        if (response.status === 204) return null;
        return await response.json();
    }

    // ---------- News ----------
    listNews()              { return this._send('GET', '/news'); }
    createNews(payload)     { return this._send('POST', '/news', payload); }
    getNews(id)             { return this._send('GET', `/news/${id}`); }
    updateNews(id, payload) { return this._send('PUT', `/news/${id}`, payload); }
    deleteNews(id)          { return this._send('DELETE', `/news/${id}`); }

    // ---------- Documents ----------
    listDocuments()                  { return this._send('GET', '/documents'); }
    createDocument(payload)          { return this._send('POST', '/documents', payload); }
    getDocument(id)                  { return this._send('GET', `/documents/${id}`); }
    updateDocument(id, payload)      { return this._send('PUT', `/documents/${id}`, payload); }
    deleteDocument(id)               { return this._send('DELETE', `/documents/${id}`); }

    // ---------- Slides ----------
    listSlides()              { return this._send('GET', '/slides'); }
    createSlide(payload)      { return this._send('POST', '/slides', payload); }
    getSlide(id)              { return this._send('GET', `/slides/${id}`); }
    updateSlide(id, payload)  { return this._send('PUT', `/slides/${id}`, payload); }
    deleteSlide(id)           { return this._send('DELETE', `/slides/${id}`); }

    // ---------- Entities ----------
    listEntities()              { return this._send('GET', '/entities'); }
    createEntity(payload)       { return this._send('POST', '/entities', payload); }
    getEntity(id)               { return this._send('GET', `/entities/${id}`); }
    updateEntity(id, payload)   { return this._send('PUT', `/entities/${id}`, payload); }
    deleteEntity(id)            { return this._send('DELETE', `/entities/${id}`); }
}

function _formatError(payload, status) {
    if (!payload) return `HTTP ${status}`;
    if (typeof payload.detail === 'string') return payload.detail;
    if (Array.isArray(payload.detail)) {
        return payload.detail.map(d => {
            const where = Array.isArray(d.loc) ? d.loc.join('.') : 'body';
            return `${where}: ${d.msg}`;
        }).join('; ');
    }
    return `HTTP ${status}`;
}
