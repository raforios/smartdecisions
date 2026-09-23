'use strict';

/**
 * Rutas — shared layer for every section of the module.
 *
 * One place for: the OPTIMIZATION endpoints of planned/executed routes, stock
 * and statistics; the wording of every error code the service answers; the
 * formatters; the Leaflet map factory; and the section switcher. Each section
 * script (`routes_plans.js`, `routes_stock.js`, …) only paints its own panel.
 */
(function () {
    const BASE = `${window.SD_CONFIG.OPTIMIZATION_URL}/v1/optimization`;
    const API = window.SD_API;

    // The service names the reason with a stable code; the sentence lives here.
    const ERRORS = {
        ROUTE_NOT_FOUND: 'Ese plan o ruta ya no existe.',
        ROUTE_CODE_ALREADY_EXISTS: 'Ya tienes un plan con ese código.',
        ROUTE_NOT_IN_CREATION: 'Sólo se puede editar o borrar un plan que está en creación.',
        INVALID_STATUS_TRANSITION: 'Ese cambio de estado no está permitido.',
        SEQUENCE_ALREADY_EXISTS: 'Ya hay una parada con ese número de orden.',
        POINT_NOT_FOUND: 'Esa parada no existe en el plan.',
        START_POINT_NOT_FOUND: 'El plan no tiene paradas.',
        PLANNED_ROUTE_NOT_ACTIVE: 'El plan no está activo.',
        OUTSIDE_START_GEOFENCE: 'Estás demasiado lejos de la primera parada para iniciar.',
        OUTSIDE_END_GEOFENCE: 'Estás demasiado lejos de la última parada para cerrar.',
        ROUTE_ALREADY_OPEN: 'La ruta ya está abierta.',
        ROUTE_ALREADY_CLOSED: 'La ruta ya está cerrada.',
        REOPEN_NOT_SAME_DAY: 'Sólo se puede reabrir una ruta el mismo día que empezó.',
        EMPTY_UPLOAD: 'El archivo está vacío.',
        UNSUPPORTED_FILE_TYPE: 'Sólo se aceptan archivos .csv o .txt.',
        INVALID_ENCODING: 'El archivo no está en UTF-8.',
        INVALID_ROW: 'Una fila tiene valores inválidos.',
        MISSING_COLUMNS: 'Al archivo le faltan columnas obligatorias.',
        NO_VISITS_TO_INFER: 'Ese vendedor no registró visitas ese día.',
        EMPTY_STOCK_LOAD: 'No hay productos en la carga.',
        DUPLICATE_SKU: 'Hay un SKU repetido en la carga.',
        STOCK_NOT_LOADED: 'Ese producto no está en el stock del día.',
        INSUFFICIENT_STOCK: 'No hay stock suficiente para esa venta.',
        ROLE_NOT_ALLOWED: 'Tu rol no permite esta acción.'
    };

    const STATUS_LABELS = {
        'IN CREATION': 'En creación', ACTIVE: 'Activo', INACTIVE: 'Inactivo'
    };
    const OUTCOME_LABELS = {
        VENTA: 'Venta', SIN_VENTA: 'Sin venta', CERRADO: 'Cerrado', NO_ENCONTRADO: 'No encontrado'
    };

    function errorText(error, fallback) {
        return ERRORS[error && error.code] || (error && error.message) || fallback;
    }

    // ---------- endpoints ----------
    const planned = {
        list: () => API.get(`${BASE}/routes/planned`),
        filter: (filters) => API.post(`${BASE}/routes/planned/filter`, filters || {}),
        get: (id) => API.get(`${BASE}/routes/planned/${encodeURIComponent(id)}`),
        create: (body) => API.post(`${BASE}/routes/planned`, body),
        update: (id, body) => API.patch(`${BASE}/routes/planned/${encodeURIComponent(id)}`, body),
        setStatus: (id, status) => API.patch(
            `${BASE}/routes/planned/${encodeURIComponent(id)}/status`, { status }
        ),
        remove: (id) => API.del(`${BASE}/routes/planned/${encodeURIComponent(id)}`),
        bulkUpload: (file) => {
            const form = new FormData();
            form.append('file', file, file.name);
            return API.postFormData(`${BASE}/routes/planned/bulk-upload`, form);
        },
        infer: (body) => API.post(`${BASE}/routes/planned/infer`, body)
    };
    const executed = {
        list: (filters) => API.get(`${BASE}/routes/executed`, filters || {}),
        get: (id) => API.get(`${BASE}/routes/executed/${encodeURIComponent(id)}`),
        start: (body) => API.post(`${BASE}/routes/executed`, body),
        report: (body) => API.post(`${BASE}/routes/executed/points`, body),
        close: (id, body) => API.patch(`${BASE}/routes/executed/${encodeURIComponent(id)}`, body),
        reopen: (id) => API.patch(`${BASE}/routes/executed/${encodeURIComponent(id)}/reopen`),
        lastLocations: (sellers) => API.get(
            `${BASE}/routes/executed/last-location?` +
            sellers.map((seller) => `sellers=${encodeURIComponent(seller)}`).join('&')
        )
    };
    const stock = {
        load: (body) => API.put(`${BASE}/stock/day`, body),
        day: (date) => API.get(`${BASE}/stock/day/${encodeURIComponent(date)}`)
    };
    const stats = {
        comparisons: (planId, filters) => API.get(
            `${BASE}/statistics/route-comparisons/${encodeURIComponent(planId)}`, filters || {}
        ),
        full: (planId, filters) => API.get(
            `${BASE}/routes/comparison/${encodeURIComponent(planId)}`, filters || {}
        ),
        pointsVisited: (seller, filters) => API.get(
            `${BASE}/statistics/sellers/${encodeURIComponent(seller)}/points-visited`, filters || {}
        )
    };

    // ---------- formatters ----------
    function escapeHtml(value) {
        return String(value == null ? '' : value)
            .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;').replaceAll("'", '&#039;');
    }
    function formatMoney(value) {
        if (value == null || isNaN(value)) return '—';
        return Number(value).toLocaleString('es-BO',
            { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    function formatDecimal(value, digits = 1) {
        if (value == null || isNaN(value)) return '—';
        return Number(value).toLocaleString('es-BO',
            { minimumFractionDigits: digits, maximumFractionDigits: digits });
    }
    function formatQuantity(value) {
        if (value == null || isNaN(value)) return '—';
        return Number.isInteger(Number(value))
            ? String(value) : formatDecimal(value, 2);
    }
    /** Local calendar date, YYYY-MM-DD — the day the operation lives in. */
    function todayIso(offsetDays = 0) {
        const now = new Date();
        now.setDate(now.getDate() + offsetDays);
        const pad = (n) => String(n).padStart(2, '0');
        return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
    }
    /** ISO 8601 with the device offset, so the service can place it on the right day. */
    function nowIso() {
        const now = new Date();
        const pad = (n) => String(n).padStart(2, '0');
        const offset = -now.getTimezoneOffset();
        const sign = offset >= 0 ? '+' : '-';
        return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}` +
            `T${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}` +
            `${sign}${pad(Math.floor(Math.abs(offset) / 60))}:${pad(Math.abs(offset) % 60)}`;
    }
    function formatStamp(iso) {
        if (!iso) return '—';
        const date = new Date(iso);
        if (isNaN(date.getTime())) return iso;
        return date.toLocaleString('es-BO', {
            day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'
        });
    }
    function timeAgo(iso) {
        const date = new Date(iso);
        if (isNaN(date.getTime())) return '—';
        const minutes = Math.round((Date.now() - date.getTime()) / 60000);
        if (minutes < 1) return 'ahora';
        if (minutes < 60) return `${minutes} min`;
        const hours = Math.floor(minutes / 60);
        if (hours < 24) return `${hours} h ${minutes % 60} min`;
        return `${Math.floor(hours / 24)} d`;
    }

    // ---------- maps ----------
    const PIN_COLORS = { plan: '#c4a378', sale: '#2d7d46', point: '#5e6580', seller: '#0d1e4c' };

    function pinIcon(label, color) {
        return window.L.divIcon({
            className: 'stop-pin-wrapper',
            html: `<span class="stop-pin" style="background:${color}">${escapeHtml(label)}</span>`,
            iconSize: [26, 26],
            iconAnchor: [13, 13]
        });
    }

    /**
     * A Leaflet map inside `elementId`, created on first use. Panels start
     * hidden, so `refresh()` re-measures the container when the panel shows.
     */
    function createMap(elementId) {
        let map = null;
        let layer = null;
        function ensure() {
            if (map) return map;
            map = window.L.map(elementId, { scrollWheelZoom: true }).setView([-16.5, -68.13], 12);
            window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                maxZoom: 19, attribution: '&copy; OpenStreetMap'
            }).addTo(map);
            layer = window.L.layerGroup().addTo(map);
            return map;
        }
        return {
            ensure,
            clear() { ensure(); layer.clearLayers(); },
            marker(lat, lon, label, color, popupHtml) {
                ensure();
                const marker = window.L.marker([lat, lon], { icon: pinIcon(label, color) });
                if (popupHtml) marker.bindPopup(popupHtml);
                marker.addTo(layer);
                return marker;
            },
            line(points, color, dashed) {
                ensure();
                window.L.polyline(points, {
                    color, weight: dashed ? 2 : 4, opacity: 0.85, dashArray: dashed ? '6 6' : null
                }).addTo(layer);
            },
            fit(points) {
                ensure();
                if (!points.length) return;
                map.fitBounds(window.L.latLngBounds(points), { padding: [30, 30] });
            },
            refresh() { setTimeout(() => { if (map) map.invalidateSize(); }, 0); }
        };
    }

    // ---------- sections ----------
    const shown = {};
    function onShow(section, callback) {
        (shown[section] = shown[section] || []).push(callback);
    }
    function showSection(name) {
        document.querySelectorAll('.routes-section').forEach((panel) => {
            panel.hidden = panel.dataset.section !== name;
        });
        document.querySelectorAll('#sectionMenu .analysis-card').forEach((card) => {
            card.classList.toggle('is-active', card.dataset.section === name);
        });
        (shown[name] || []).forEach((callback) => callback());
    }
    document.addEventListener('DOMContentLoaded', () => {
        const menu = document.getElementById('sectionMenu');
        if (!menu) return;
        menu.addEventListener('click', (event) => {
            const card = event.target.closest('.analysis-card');
            if (card) showSection(card.dataset.section);
        });
    });

    /** Parameter for a note element: paints a form-note as success or error. */
    function note(element, text, kind) {
        element.className = 'form-note' + (kind ? ` ${kind}` : '');
        element.textContent = text || '';
    }

    window.SD_TRACK = {
        planned, executed, stock, stats,
        errorText, STATUS_LABELS, OUTCOME_LABELS, PIN_COLORS,
        escapeHtml, formatMoney, formatDecimal, formatQuantity,
        todayIso, nowIso, formatStamp, timeAgo,
        createMap, onShow, showSection, note
    };
})();
