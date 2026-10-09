/**
 * BillingService — every call the counter makes, in one place.
 *
 * The backend answers with data and stable codes; the wording of every code
 * lives here, so no screen shows a SCREAMING_SNAKE to a cashier.
 */
import { resolveBases, request } from './apiClient.js';
import { getToken } from '../auth.js';
import { BILLING_URL, BILLING_URL_LOCAL } from '../config.js';

const BASES = resolveBases({ remote: BILLING_URL, local: BILLING_URL_LOCAL });
const ROOT = '/v1/billing';

/** What each code the service can answer means for the person reading it. */
export const ERRORS = {
    SKU_ALREADY_EXISTS: 'Ese código ya está en el catálogo.',
    PRODUCT_NOT_FOUND: 'Ese producto no está en el catálogo.',
    PRODUCT_INACTIVE: 'Ese producto está dado de baja.',
    LOT_NOT_FOUND: 'Ese lote ya no existe.',
    DUPLICATE_LINE: 'El producto está dos veces en la nota: súmalo en una sola línea.',
    INSUFFICIENT_STOCK: 'No hay unidades suficientes en estantería.',
    DISCOUNTS_DISABLED: 'Los descuentos están desactivados en la configuración.',
    DISCOUNT_ABOVE_LINE: 'El descuento no puede superar el importe de la línea.',
    SALE_NOT_FOUND: 'Esa nota no existe.',
    SALE_ALREADY_CANCELLED: 'Esa nota ya estaba anulada.',
    PURCHASE_NOT_FOUND: 'Esa nota de compra no existe.',
    SETTINGS_NOT_FOUND: 'Todavía no configuraste el comercio.',
    ROLE_NOT_ALLOWED: 'Tu rol no permite esta acción.',
    CASH_SESSION_ALREADY_OPEN: 'Ya tienes una caja abierta.',
    CASH_SESSION_REQUIRED: 'Abre tu caja antes de vender.',
    CASH_SESSION_CLOSED: 'Esa caja ya está cerrada.',
    CASH_SESSION_EXPIRED: 'Tu caja de un día anterior sigue abierta: ciérrala antes de seguir.',
    CASH_SESSION_NOT_FOUND: 'No hay una caja abierta.',
    CLOSING_NOTE_REQUIRED: 'Para cerrar la caja de otra persona escribe una observación.',
    EXPENSE_EXCEEDS_CASH: 'El egreso supera el efectivo que hay en la caja.',
    EXPENSE_NOT_FOUND: 'Ese egreso no existe o ya estaba anulado.'
};

/** What each payment method is called on screen. */
export const PAYMENT_LABELS = {
    EFECTIVO: 'Efectivo',
    QR: 'QR',
    TARJETA_DEBITO: 'Tarjeta de débito',
    TARJETA_CREDITO: 'Tarjeta de crédito',
    TARJETA: 'Tarjeta sin detalle'
};

/** The methods offered when selling: card without detail belongs to old notes. */
export const SALE_PAYMENT_METHODS = ['EFECTIVO', 'QR', 'TARJETA_DEBITO', 'TARJETA_CREDITO'];

/** What each expense type is called on screen. */
export const EXPENSE_LABELS = {
    SUPPLIER_PAYMENT: 'Pago a proveedor',
    SERVICE_PAYMENT: 'Pago de servicio',
    PETTY_CASH: 'Caja chica'
};

/** The sentence for an error, or the fallback when the code is unknown. */
export function errorText(error, fallback) {
    return ERRORS[error?.code] || error?.message || fallback;
}

async function call(path, options = {}) {
    const headers = Object.assign(
        { Accept: 'application/json' },
        options.body ? { 'Content-Type': 'application/json' } : {},
        options.headers || {}
    );
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;

    const response = await request(BASES, `${ROOT}${path}`, { ...options, headers });

    let payload = null;
    if ((response.headers.get('content-type') || '').includes('application/json')) {
        try { payload = await response.json(); } catch (_) { /* cuerpo vacío */ }
    }
    if (!response.ok) {
        const detail = payload?.detail;
        const error = new Error(detail || `Error ${response.status} en el servicio.`);
        error.status = response.status;
        if (typeof detail === 'string' && /^[A-Z][A-Z0-9_]+$/.test(detail)) {
            error.code = detail;
        }
        throw error;
    }
    return payload;
}

const query = (params) => {
    const search = new URLSearchParams(
        Object.entries(params || {}).filter(([, value]) => value !== null && value !== '')
    ).toString();
    return search ? `?${search}` : '';
};

export const BillingService = {
    dashboard: (params) => call(`/dashboard${query(params)}`),

    getSettings: () => call('/settings'),
    saveSettings: (body) => call('/settings', { method: 'PUT', body: JSON.stringify(body) }),

    listProducts: (params) => call(`/products${query(params)}`),
    getProduct: (sku) => call(`/products/${encodeURIComponent(sku)}`),
    createProduct: (body) => call('/products', { method: 'POST', body: JSON.stringify(body) }),
    updateProduct: (sku, body) => call(`/products/${encodeURIComponent(sku)}`,
                                       { method: 'PATCH', body: JSON.stringify(body) }),

    lots: (sku, params) => call(`/products/${encodeURIComponent(sku)}/lots${query(params)}`),
    repriceLot: (sku, lotId, salePrice) => call(
        `/products/${encodeURIComponent(sku)}/lots/${encodeURIComponent(lotId)}`,
        { method: 'PATCH', body: JSON.stringify({ sale_price: salePrice }) }
    ),

    listPurchases: (params) => call(`/purchases${query(params)}`),
    getPurchase: (id) => call(`/purchases/${encodeURIComponent(id)}`),
    receivePurchase: (body) => call('/purchases', { method: 'POST', body: JSON.stringify(body) }),

    listSales: (params) => call(`/sales${query(params)}`),
    getSale: (id) => call(`/sales/${encodeURIComponent(id)}`),
    issueSale: (body) => call('/sales', { method: 'POST', body: JSON.stringify(body) }),
    cancelSale: (id) => call(`/sales/${encodeURIComponent(id)}/cancel`, { method: 'POST' }),

    openTill: (openingCash) => call('/cash/sessions', {
        method: 'POST', body: JSON.stringify({ opening_cash: openingCash })
    }),
    currentTill: () => call('/cash/sessions/current'),
    listTills: (params) => call(`/cash/sessions${query(params)}`),
    getTill: (id) => call(`/cash/sessions/${encodeURIComponent(id)}`),
    addExpense: (id, body) => call(`/cash/sessions/${encodeURIComponent(id)}/expenses`,
                                   { method: 'POST', body: JSON.stringify(body) }),
    cancelExpense: (id, movementId) => call(
        `/cash/sessions/${encodeURIComponent(id)}/expenses/${encodeURIComponent(movementId)}/cancel`,
        { method: 'POST' }
    ),
    closeTill: (id, body) => call(`/cash/sessions/${encodeURIComponent(id)}/close`,
                                  { method: 'POST', body: JSON.stringify(body) }),
    tillAlerts: () => call('/cash/alerts')
};

/**
 * The user's open till, or null if they have none. A 404 is not an error
 * here: it is the answer «you have not opened the till yet».
 */
export async function currentTillOrNull() {
    try {
        return await BillingService.currentTill();
    } catch (error) {
        if (error.code === 'CASH_SESSION_NOT_FOUND') return null;
        throw error;
    }
}
