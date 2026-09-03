'use strict';

/**
 * Rutas de visita — module logic.
 *
 * The plan comes from the sales dataset the user already uploaded in the Excel
 * module: same `dataset_id`, read from sessionStorage. There is no route_id or
 * day to type in — the days are derived from where the clients are, which is
 * what makes this module work with any client's file.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.requireAuth()) return;

    const { qs, toast, setButtonBusy } = window.SD_UI;

    qs('#userChip').textContent = window.SD_AUTH.getEmail() || 'usuario';
    qs('#logoutButton').addEventListener('click', () => window.SD_AUTH.logout());

    const OPTIMIZATION_URL = window.SD_CONFIG.OPTIMIZATION_URL;
    // Shared with the Excel module on purpose: one upload feeds every analysis.
    const DATASET_KEY = 'sd_excel_dataset_id';

    // Tier arrives as a code; colour and wording belong to the UI.
    const TIER_COLOR = { HIGH: '#2d7d46', MEDIUM: '#c4a378', LOW: '#5e6580' };
    const TIER_LABELS = { HIGH: 'Alto', MEDIUM: 'Medio', LOW: 'Bajo' };

    // The service reports why it cannot build a plan with a stable code; the
    // sentence belongs here, like every other label.
    const ROUTE_ERRORS = {
        MISSING_COORDINATES: 'El archivo no tiene coordenadas. Agrega las columnas ' +
            'Latitud y Longitud para usar el módulo de rutas.',
        NO_GEOCODED_CLIENTS: 'No hay clientes con coordenadas válidas para ese filtro.',
        EMPTY_PERIOD: 'No hay ventas en el período seleccionado.',
        EMPTY_UPLOAD: 'El archivo que subiste está vacío.',
        EMPTY_CSV: 'El archivo CSV está vacío.',
        EMPTY_POINT_LIST: 'La lista de puntos está vacía.',
        INVALID_ROW: 'Una fila del archivo tiene valores inválidos.',
        INVALID_POINT: 'Un punto del archivo tiene valores inválidos.',
        ROUTING_SERVICE_UNAVAILABLE: 'El servicio de ruteo vial (OSRM) no está disponible.',
        ROUTING_SERVICE_NO_ROUTE: 'No se encontró una ruta por calles para ese tramo.'
    };

    function errorText(error, fallback) {
        return ROUTE_ERRORS[error && error.code] || (error && error.message) || fallback;
    }
    const ROUTE_COLOR = '#0d1e4c';

    const state = { datasetId: sessionStorage.getItem(DATASET_KEY), plan: null, day: null };
    let map = null;
    let layer = null;

    if (!state.datasetId) {
        qs('#noDataset').hidden = false;
        return;
    }
    qs('#plannerLayout').hidden = false;

    // ---------- Map ----------
    function ensureMap() {
        if (map) return map;
        map = window.L.map('map', { scrollWheelZoom: true }).setView([-16.5, -68.13], 13);
        window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '&copy; OpenStreetMap'
        }).addTo(map);
        layer = window.L.layerGroup().addTo(map);
        return map;
    }

    /**
     * Leaflet measures its container on creation. The map lives inside a panel
     * that starts hidden, so without this the tiles render into a zero-sized box
     * and the map stays grey — the "se queda en modo carga" bug.
     */
    function refreshMapSize() {
        setTimeout(() => { if (map) map.invalidateSize(); }, 0);
    }

    function numberedIcon(stop) {
        const color = TIER_COLOR[stop.segment] || TIER_COLOR.LOW;
        return window.L.divIcon({
            className: 'stop-pin-wrapper',
            html: `<span class="stop-pin" style="background:${color}">${stop.stop_order}</span>`,
            iconSize: [26, 26],
            iconAnchor: [13, 13]
        });
    }

    function drawDay(day) {
        ensureMap();
        layer.clearLayers();

        const stops = day.stops || [];
        if (!stops.length) return;

        stops.forEach((stop) => {
            window.L.marker([stop.latitude, stop.longitude], { icon: numberedIcon(stop) })
                .bindPopup(
                    `<strong>${stop.stop_order}. ${escapeHtml(stop.client)}</strong><br>` +
                    `Valor: ${escapeHtml(stop.segment)}<br>` +
                    `Compró Bs ${formatMoney(stop.amount)}<br>` +
                    `Última compra: ${escapeHtml(stop.last_purchase || '—')}`
                )
                .addTo(layer);
        });

        // The backend returns [lon, lat] along the streets; Leaflet wants
        // [lat, lon]. When OSRM could not be reached the geometry is empty and
        // we join the stops directly — a straight line is a degraded map, an
        // empty one is a broken module.
        const road = (day.geometry || []).map((pair) => [pair[1], pair[0]]);
        const path = road.length ? road : stops.map((stop) => [stop.latitude, stop.longitude]);
        window.L.polyline(path, {
            color: ROUTE_COLOR, weight: road.length ? 4 : 2,
            opacity: 0.85, dashArray: road.length ? null : '6 6'
        }).addTo(layer);

        map.fitBounds(window.L.latLngBounds(
            stops.map((stop) => [stop.latitude, stop.longitude])
        ), { padding: [30, 30] });
        refreshMapSize();
    }

    // ---------- Rendering ----------
    function renderDayList(plan) {
        const list = qs('#dayList');
        list.innerHTML = '';
        plan.days.forEach((day) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'day-chip' + (day.day === state.day ? ' is-active' : '');
            button.dataset.day = String(day.day);
            button.innerHTML =
                `<span class="day-chip-title">Día ${day.day}</span>` +
                `<span class="day-chip-meta">${day.stops.length} paradas · ` +
                `${formatDecimal(day.distance_km)} km</span>`;
            list.appendChild(button);
        });
        qs('#daysCard').hidden = false;
        qs('#legendCard').hidden = false;
    }

    function renderDaySummary(day) {
        const hours = Math.floor(day.duration_min / 60);
        const minutes = Math.round(day.duration_min % 60);
        qs('#daySummary').innerHTML =
            metric('Paradas', String(day.stops.length)) +
            metric('Recorrido', `${formatDecimal(day.distance_km)} km`) +
            metric('Tiempo en ruta', hours ? `${hours} h ${minutes} min` : `${minutes} min`) +
            metric('Compra del día', `Bs ${formatMoney(day.total_amount)}`);
        qs('#daySummary').hidden = false;
    }

    function metric(label, value) {
        return `<div class="metric"><p class="metric-label">${escapeHtml(label)}</p>` +
               `<p class="metric-value">${escapeHtml(value)}</p></div>`;
    }

    function renderStops(day) {
        const tbody = qs('#stopsTable tbody');
        tbody.innerHTML = '';
        day.stops.forEach((stop) => {
            const row = document.createElement('tr');
            row.innerHTML =
                `<td class="numeric">${stop.stop_order}</td>` +
                `<td>${escapeHtml(stop.client)}</td>` +
                `<td><span class="tier-badge tier-${stop.segment.toLowerCase()}">` +
                `${escapeHtml(TIER_LABELS[stop.segment] || stop.segment)}</span></td>` +
                `<td class="numeric">Bs ${formatMoney(stop.amount)}</td>` +
                `<td class="numeric">${escapeHtml(stop.last_purchase || '—')}</td>`;
            tbody.appendChild(row);
        });
        qs('#stopsCard').hidden = false;
    }

    function selectDay(dayNumber) {
        const day = state.plan.days.find((item) => item.day === dayNumber);
        if (!day) return;
        state.day = dayNumber;
        renderDayList(state.plan);
        renderDaySummary(day);
        renderStops(day);
        drawDay(day);
    }

    qs('#dayList').addEventListener('click', (event) => {
        const chip = event.target.closest('.day-chip');
        if (chip) selectDay(Number(chip.dataset.day));
    });

    // ---------- Plan request ----------
    async function buildPlan() {
        const note = qs('#formNote');
        note.className = 'form-note';
        note.textContent = 'Agrupando clientes y calculando el recorrido…';
        const done = setButtonBusy(qs('#planButton'), 'Calculando…');

        try {
            const params = { days: qs('#daysSelect').value };
            const seller = qs('#sellerSelect').value;
            if (seller) params.seller = seller;
            if (qs('#planFrom').value) params.date_from = qs('#planFrom').value;
            if (qs('#planTo').value) params.date_to = qs('#planTo').value;

            const plan = await window.SD_API.get(
                `${OPTIMIZATION_URL}/v1/optimization/plan/` +
                `${encodeURIComponent(state.datasetId)}`,
                params
            );
            if (!plan.days || !plan.days.length) {
                throw new Error('No se pudo armar ninguna ruta con esos filtros.');
            }

            state.plan = plan;
            fillSellers(plan.sellers, seller);
            qs('#mapOverlay').hidden = true;
            selectDay(plan.days[0].day);

            note.classList.add('success');
            note.textContent = `${plan.total_clients} clientes repartidos en ` +
                `${plan.days.length} días.`;
        } catch (error) {
            note.classList.add('error');
            note.textContent = errorText(error, 'No se pudieron armar las rutas.');
            toast(errorText(error, 'Error al armar las rutas.'), 'error');
        } finally {
            done();
        }
    }

    function fillSellers(sellers, selected) {
        const select = qs('#sellerSelect');
        if (!sellers || !sellers.length || select.dataset.filled) return;
        sellers.forEach((seller) => {
            const option = document.createElement('option');
            option.value = seller;
            option.textContent = seller;
            select.appendChild(option);
        });
        select.dataset.filled = '1';
        if (selected) select.value = selected;
    }

    qs('#planButton').addEventListener('click', buildPlan);

    // ---------- helpers ----------
    function formatMoney(value) {
        if (value == null || isNaN(value)) return '—';
        return Number(value).toLocaleString('es-BO',
            { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    function formatDecimal(value) {
        if (value == null || isNaN(value)) return '—';
        return Number(value).toLocaleString('es-BO',
            { minimumFractionDigits: 1, maximumFractionDigits: 1 });
    }

    function escapeHtml(value) {
        return String(value == null ? '' : value)
            .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;').replaceAll("'", '&#039;');
    }

    window.SD_SESSION.mountChip(
        'sessionChip',
        'El plan que estás viendo se vuelve a calcular al entrar de nuevo.'
    );

    // Kick off with a plan so the module is never an empty screen.
    buildPlan();
});
