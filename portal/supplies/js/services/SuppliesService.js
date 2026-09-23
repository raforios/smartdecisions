/**
 * SuppliesService — wraps every /v1/supplies/* endpoint exposed by the
 * backend so pages can call it as a flat, typed-looking object.
 *
 * Endpoint groups:
 *   - Catalog: categories (accounting groups), units, items.
 *   - Suppliers: the vendors a Nota de Ingreso is issued against.
 *   - Requests: lifecycle (create/list/get/delete + transitions).
 *   - Kardex: per-item ledger, manual adjustments.
 *   - Reports & Dashboard.
 */
import { authHeader, parseJsonOrThrow, request, resolveBases } from './apiClient.js';

export class SuppliesService {
    constructor({ suppliesBaseUrl, suppliesBaseUrlFallback } = {}) {
        this.bases = resolveBases({
            remote: suppliesBaseUrl,
            local: suppliesBaseUrlFallback,
        });
    }

    async _send(path, { method = 'GET', body, query } = {}) {
        const url = path + (query ? this._buildQuery(query) : '');
        const init = {
            method,
            headers: {
                ...authHeader(),
                ...(body ? { 'Content-Type': 'application/json' } : {}),
            },
        };
        if (body !== undefined) init.body = JSON.stringify(body);
        const response = await request(this.bases, url, init);
        return parseJsonOrThrow(response);
    }

    _buildQuery(params) {
        const usp = new URLSearchParams();
        Object.entries(params).forEach(([key, value]) => {
            if (value === undefined || value === null || value === '') return;
            usp.append(key, value);
        });
        const qs = usp.toString();
        return qs ? `?${qs}` : '';
    }

    // ----------------------- Categories ----------------------- //
    listCategories(params = {}) {
        return this._send('/categories', { query: params });
    }
    createCategory(payload) {
        return this._send('/categories', { method: 'POST', body: payload });
    }
    updateCategory(id, payload) {
        return this._send(`/categories/${id}`, { method: 'PUT', body: payload });
    }
    deleteCategory(id) {
        return this._send(`/categories/${id}`, { method: 'DELETE' });
    }

    // ----------------------- Units ---------------------------- //
    listUnits(params = {}) {
        return this._send('/units', { query: params });
    }
    createUnit(payload) {
        return this._send('/units', { method: 'POST', body: payload });
    }
    updateUnit(id, payload) {
        return this._send(`/units/${id}`, { method: 'PUT', body: payload });
    }
    deleteUnit(id) {
        return this._send(`/units/${id}`, { method: 'DELETE' });
    }

    // ----------------------- Items ---------------------------- //
    listItems(params = {}) {
        return this._send('/items', { query: params });
    }
    getItem(id) {
        return this._send(`/items/${id}`);
    }
    createItem(payload) {
        return this._send('/items', { method: 'POST', body: payload });
    }
    updateItem(id, payload) {
        return this._send(`/items/${id}`, { method: 'PUT', body: payload });
    }
    updateItemParameters(id, payload) {
        return this._send(`/items/${id}/parameters`, { method: 'PUT', body: payload });
    }
    deleteItem(id) {
        return this._send(`/items/${id}`, { method: 'DELETE' });
    }

    // ----------------------- Suppliers ------------------------ //
    listSuppliers(params = {}) {
        return this._send('/suppliers', { query: params });
    }
    getSupplier(id) {
        return this._send(`/suppliers/${id}`);
    }
    createSupplier(payload) {
        return this._send('/suppliers', { method: 'POST', body: payload });
    }
    updateSupplier(id, payload) {
        return this._send(`/suppliers/${id}`, { method: 'PUT', body: payload });
    }
    deleteSupplier(id) {
        return this._send(`/suppliers/${id}`, { method: 'DELETE' });
    }

    // ----------------------- Entries (Nota de Ingreso) -------- //
    listEntries(params = {}) {
        return this._send('/entries', { query: params });
    }
    getEntry(id) {
        return this._send(`/entries/${id}`);
    }
    createEntry(payload) {
        return this._send('/entries', { method: 'POST', body: payload });
    }

    // ----------------------- Requests ------------------------- //
    listRequests(params = {}) {
        return this._send('/requests', { query: params });
    }
    getRequest(id) {
        return this._send(`/requests/${id}`);
    }
    createRequest(payload) {
        return this._send('/requests', { method: 'POST', body: payload });
    }
    deleteRequest(id) {
        return this._send(`/requests/${id}`, { method: 'DELETE' });
    }
    processRequest(id) {
        return this._send(`/requests/${id}/process`, { method: 'PATCH' });
    }
    deliverRequest(id, payload = {}) {
        return this._send(`/requests/${id}/deliver`, {
            method: 'PATCH', body: payload,
        });
    }
    closeRequest(id) {
        return this._send(`/requests/${id}/close`, { method: 'PATCH' });
    }
    rejectRequest(id, reason) {
        return this._send(`/requests/${id}/reject`, {
            method: 'PATCH', body: { reason },
        });
    }
    cancelRequest(id, reason) {
        return this._send(`/requests/${id}/cancel`, {
            method: 'PATCH', body: { reason },
        });
    }

    // ----------------------- Kardex --------------------------- //
    listKardexForItem(itemId, params = {}) {
        return this._send(`/kardex/items/${itemId}`, { query: params });
    }
    createKardexAdjustment(payload) {
        return this._send('/kardex/adjustments', { method: 'POST', body: payload });
    }

    // ----------------------- Reports & Dashboard -------------- //
    reportLowStock() {
        return this._send('/reports/low-stock');
    }
    reportEntries(params = {}) {
        return this._send('/reports/entries', { query: params });
    }
    reportRequests(params = {}) {
        return this._send('/reports/requests', { query: params });
    }
    reportPhysicalValued(params = {}) {
        return this._send('/reports/inventory/physical-valued', { query: params });
    }
    reportStockOnHand(params = {}) {
        return this._send('/reports/inventory/stock-on-hand', { query: params });
    }
    reportInOutByGroup(params = {}) {
        return this._send('/reports/inventory/in-out-by-group', { query: params });
    }
    reportKardexValued(params = {}) {
        return this._send('/reports/kardex-valued', { query: params });
    }
    reportOutflowStats(params = {}) {
        return this._send('/reports/outflow-stats', { query: params });
    }
    dashboardSummary() {
        return this._send('/dashboard/summary');
    }
    dashboardRecentActivity(limit = 10) {
        return this._send('/dashboard/recent-activity', { query: { limit } });
    }
}
