'use strict';

/**
 * Optimización de rutas — Leaflet + OSM frontend module.
 *
 * Pipeline:
 *   1. Usuario ingresa route_id + day + radio.
 *   2. Click "Cargar puntos" → GET /v1/optimization/data_model → markers + ruta
 *      original (polyline en orden client_id).
 *   3. Click "Optimizar"     → GET /v1/optimization/optimal_route → polyline
 *      con el orden propuesto por la heurística + métricas (paradas, distancia
 *      total, distancia promedio por segmento).
 *
 * El backend (services/optimization/) ya proyecta la ruta sobre el grafo OSM
 * usando osmnx; aquí dibujamos los segmentos lineales (origin→target con sus
 * coords) por simplicidad y costo cero de tiles. Para el road-aligned exacto
 * habría que extender el backend para retornar lat/lng de cada OSM node.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.requireAuth()) return;

    const { qs, qsAll, toast, setButtonBusy } = window.SD_UI;

    qs('#userChip').textContent = window.SD_AUTH.getEmail() || 'usuario';
    qs('#logoutButton').addEventListener('click', () => window.SD_AUTH.logout());

    const OPT_URL = window.SD_CONFIG.OPTIMIZATION_URL;

    // ---------- Map setup ----------
    const map = L.map('map', {
        center: [-16.5000, -68.1500], // La Paz default
        zoom: 14,
        zoomControl: true,
        attributionControl: true
    });

    // CartoDB Voyager tiles — light + color, matches the corporate theme.
    const baseTiles = L.tileLayer('https://{s}.basemaps.cartocdn.com/voyager/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://openstreetmap.org">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 19
    }).addTo(map);

    // Tile fallback: if the CartoDB CDN is unreachable, swap to the standard OSM
    // tiles once so the map never renders as a blank grey canvas.
    let tilesFellBack = false;
    baseTiles.on('tileerror', () => {
        if (tilesFellBack) return;
        tilesFellBack = true;
        map.removeLayer(baseTiles);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://openstreetmap.org">OpenStreetMap</a> contributors',
            maxZoom: 19
        }).addTo(map);
    });

    // Leaflet miscomputes its size when the map div is laid out (flex/grid) after
    // init, which shows as a grey box with the markers/lines piled up. Force a
    // recalculation once the layout settles and on every resize.
    function refreshMapSize() { map.invalidateSize(false); }
    requestAnimationFrame(refreshMapSize);
    setTimeout(refreshMapSize, 300);
    window.addEventListener('resize', refreshMapSize);

    const layers = {
        points: L.layerGroup().addTo(map),
        original: L.layerGroup().addTo(map),
        optimized: L.layerGroup().addTo(map)
    };

    const state = {
        points: [],     // [{day, client_id, y, x, color}, ...]
        segments: [],   // optimized result
        routeId: null,
        day: null,
        dist: null
    };

    // ---------- Layer toggles ----------
    function bindToggle(toggleId, layerKey) {
        qs('#' + toggleId).addEventListener('change', (event) => {
            const layer = layers[layerKey];
            if (event.target.checked) map.addLayer(layer);
            else map.removeLayer(layer);
        });
    }
    bindToggle('togglePoints', 'points');
    bindToggle('toggleOriginal', 'original');
    bindToggle('toggleOptimized', 'optimized');

    // ---------- Loader helpers ----------
    function showLoader(text) {
        qs('#mapLoaderText').textContent = text || 'Cargando…';
        qs('#mapLoader').hidden = false;
    }
    function hideLoader() { qs('#mapLoader').hidden = true; }

    function setNote(message, variant) {
        const note = qs('#formNote');
        note.className = 'form-note' + (variant ? ' ' + variant : '');
        note.textContent = message || '';
    }

    function readForm() {
        const form = qs('#routeForm');
        return {
            route_id: Number(form.elements.route_id.value),
            day: Number(form.elements.day.value),
            dist: Number(form.elements.dist.value)
        };
    }

    // ---------- Drawing ----------
    function clearAll() {
        layers.points.clearLayers();
        layers.original.clearLayers();
        layers.optimized.clearLayers();
    }

    function colorFor(point) {
        if (point.color === 'red') return '#c0392b';
        if (point.color === 'green') return '#2d7d46';
        return '#c8941d';
    }

    function drawPoints(points) {
        layers.points.clearLayers();
        points.forEach((point) => {
            L.circleMarker([point.y, point.x], {
                radius: point.color === 'red' || point.color === 'green' ? 9 : 7,
                color: '#ffffff',
                weight: 2,
                fillColor: colorFor(point),
                fillOpacity: 0.95
            })
                .bindPopup(
                    `<strong>Cliente ${point.client_id}</strong><br>` +
                    `día ${point.day}<br>` +
                    `lat ${point.y.toFixed(5)}, lng ${point.x.toFixed(5)}`
                )
                .addTo(layers.points);
        });

        if (points.length === 0) return;
        const bounds = L.latLngBounds(points.map((p) => [p.y, p.x]));
        map.fitBounds(bounds, { padding: [40, 40] });
    }

    function drawOriginalRoute(points) {
        layers.original.clearLayers();
        if (points.length < 2) return;
        // Visit order is the dataset's client_id order; mirrors the legacy notebook.
        const sorted = [...points].sort((a, b) => a.client_id - b.client_id);
        const latlngs = sorted.map((p) => [p.y, p.x]);
        L.polyline(latlngs, {
            color: '#7a4a2a',
            weight: 3,
            opacity: 0.85,
            dashArray: '6 6'
        })
            .bindPopup('Ruta original (orden client_id)')
            .addTo(layers.original);
    }

    function drawOptimizedRoute(segments) {
        layers.optimized.clearLayers();
        if (segments.length === 0) return;
        // Each segment carries (y, x) and (y_next, x_next): the linear hop between
        // two consecutive stops in the optimized visit order.
        segments.forEach((seg) => {
            L.polyline([[seg.y, seg.x], [seg.y_next, seg.x_next]], {
                color: '#0d1e4c',
                weight: 4,
                opacity: 0.95
            })
                .bindPopup(
                    `<strong>${seg.origin} → ${seg.target}</strong><br>` +
                    `distance (graph): ${seg.distance.toFixed(1)} m<br>` +
                    `linear: ${seg.time_seg.toFixed(1)} m`
                )
                .addTo(layers.optimized);
        });
    }

    function renderSummary(segments) {
        const card = qs('#summaryCard');
        if (segments.length === 0) {
            card.hidden = true;
            return;
        }
        const totalDistance = segments.reduce((acc, s) => acc + (s.distance || 0), 0);
        const totalLinear = segments.reduce((acc, s) => acc + (s.time_seg || 0), 0);
        const stops = new Set();
        segments.forEach((s) => { stops.add(s.origin); stops.add(s.target); });
        const avgSegment = segments.length ? totalLinear / segments.length : 0;

        const cards = [
            { label: 'Paradas', value: String(stops.size), variant: 'accent' },
            { label: 'Segmentos', value: String(segments.length) },
            { label: 'Distancia total', value: formatMeters(totalDistance), variant: 'accent' },
            { label: 'Lineal total', value: formatMeters(totalLinear) },
            { label: 'Promedio / tramo', value: formatMeters(avgSegment) },
            { label: 'OSM radio', value: `${state.dist} m` }
        ];
        const container = qs('#summaryMetrics');
        container.innerHTML = '';
        cards.forEach((card) => {
            const node = document.createElement('div');
            node.className = 'metric';
            node.innerHTML = `
                <p class="metric-label">${escapeHtml(card.label)}</p>
                <p class="metric-value ${card.variant || ''}">${escapeHtml(card.value)}</p>
            `;
            container.appendChild(node);
        });
        card.hidden = false;
    }

    function formatMeters(value) {
        if (value == null || Number.isNaN(value)) return '—';
        if (value >= 1000) return `${(value / 1000).toFixed(2)} km`;
        return `${Math.round(value)} m`;
    }
    function escapeHtml(value) {
        return String(value)
            .replaceAll('&', '&amp;').replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;').replaceAll('"', '&quot;')
            .replaceAll("'", '&#039;');
    }

    // ---------- CSV upload ----------
    const routeFileInput = qs('#routeFileInput');
    const routeUploadZone = qs('#routeUploadZone');
    const routeFileChip = qs('#routeFileChip');
    const routeUploadButton = qs('#routeUploadButton');
    const routeUploadNote = qs('#routeUploadNote');
    let stagedRouteFile = null;

    qs('#routeChooseLink').addEventListener('click', (event) => {
        event.preventDefault();
        routeFileInput.click();
    });
    routeFileInput.addEventListener('change', () => {
        const file = routeFileInput.files && routeFileInput.files[0];
        if (file) stageRouteFile(file);
    });
    ['dragenter', 'dragover'].forEach((eventName) => {
        routeUploadZone.addEventListener(eventName, (event) => {
            event.preventDefault();
            routeUploadZone.classList.add('dragover');
        });
    });
    ['dragleave', 'drop'].forEach((eventName) => {
        routeUploadZone.addEventListener(eventName, (event) => {
            event.preventDefault();
            routeUploadZone.classList.remove('dragover');
        });
    });
    routeUploadZone.addEventListener('drop', (event) => {
        const file = event.dataTransfer.files && event.dataTransfer.files[0];
        if (file) stageRouteFile(file);
    });
    routeUploadZone.addEventListener('click', (event) => {
        // Avoid double-trigger when clicking the inner anchor.
        if (event.target.id === 'routeChooseLink') return;
        routeFileInput.click();
    });

    function stageRouteFile(file) {
        if (!/\.(csv|txt)$/i.test(file.name)) {
            setRouteUploadNote('Solo se aceptan .csv o .txt.', 'error');
            return;
        }
        stagedRouteFile = file;
        routeFileChip.hidden = false;
        routeFileChip.textContent = `${file.name} · ${formatBytes(file.size)}`;
        routeUploadButton.disabled = false;
        setRouteUploadNote('', '');
    }

    function setRouteUploadNote(message, variant) {
        routeUploadNote.className = 'form-note' + (variant ? ' ' + variant : '');
        routeUploadNote.textContent = message || '';
    }

    function formatBytes(bytes) {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }

    // Download a CSV template the user can fill in.
    qs('#routeSampleButton').addEventListener('click', () => {
        const sample = [
            'route_id,day,client_id,latitude,longitude,client',
            '2,1,101,-16.5000,-68.1500,Tienda Doña Rosa',
            '2,1,102,-16.5050,-68.1450,Mini-market El Sol',
            '2,1,103,-16.5100,-68.1400,Bodega Lupita',
            '2,1,104,-16.5070,-68.1525,Almacén San Pedro',
            '2,1,105,-16.4980,-68.1455,Tienda Esquina'
        ].join('\n');
        const blob = new Blob([sample], { type: 'text/csv;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'plantilla_puntos_ruta.csv';
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        setRouteUploadNote('Plantilla descargada. Completá tus puntos y volvé a subir.', 'success');
    });

    routeUploadButton.addEventListener('click', async () => {
        if (!stagedRouteFile) return;
        const done = setButtonBusy(routeUploadButton, 'Subiendo…');
        setRouteUploadNote('Subiendo CSV…', '');
        showLoader('Subiendo CSV…');
        try {
            const formData = new FormData();
            formData.append('file', stagedRouteFile);
            const response = await window.SD_API.postFormData(
                `${OPT_URL}/v1/optimization/routes/bulk-upload`,
                formData
            );
            const writtenRoute = response.route_id;
            const writtenDay = response.day;
            const writtenCount = response.points_written;
            // Mirror the just-uploaded (route_id, day) onto the form so a
            // subsequent "Cargar puntos" hits the same partition.
            const form = qs('#routeForm');
            form.elements.route_id.value = writtenRoute;
            form.elements.day.value = writtenDay;
            setRouteUploadNote(
                `OK — ${writtenCount} punto(s) escritos para route_id=${writtenRoute}, day=${writtenDay}.`,
                'success'
            );
            toast(`CSV subido: ${writtenCount} punto(s).`, 'success');
            // Auto-trigger the existing load flow so the map updates right away.
            qs('#loadPointsButton').click();
        } catch (error) {
            setRouteUploadNote(error.message || 'Error al subir el CSV.', 'error');
            toast(error.message || 'Error al subir el CSV.', 'error');
        } finally {
            hideLoader();
            done();
        }
    });

    // ---------- API actions ----------
    qs('#loadPointsButton').addEventListener('click', async () => {
        const params = readForm();
        if (!params.route_id || params.day < 0) {
            setNote('Completa route_id y day antes de cargar.', 'error');
            return;
        }
        setNote('Consultando data_model…');
        showLoader('Cargando puntos…');
        const button = qs('#loadPointsButton');
        const done = setButtonBusy(button, 'Cargando…');
        try {
            // GET helper from api.js — the response is a normalized JSON array.
            const data = await window.SD_API.get(
                `${OPT_URL}/v1/optimization/data_model`,
                { route_id: params.route_id, day: params.day }
            );
            const points = Array.isArray(data) ? data : (data.data || []);
            state.points = points;
            state.routeId = params.route_id;
            state.day = params.day;
            state.dist = params.dist;

            clearAll();
            drawPoints(points);
            drawOriginalRoute(points);
            qs('#optimizeButton').disabled = points.length < 2;
            qs('#summaryCard').hidden = true;
            setNote(`${points.length} punto(s) cargados.`, 'success');
        } catch (error) {
            setNote(error.message || 'Error al cargar puntos.', 'error');
            toast(error.message || 'Error al cargar.', 'error');
        } finally {
            hideLoader();
            done();
        }
    });

    qs('#optimizeButton').addEventListener('click', async () => {
        if (state.points.length < 2) return;
        const params = readForm();
        state.dist = params.dist;
        setNote('Ejecutando heurística + osmnx en el backend (puede tardar)…');
        showLoader('Optimizando…');
        const button = qs('#optimizeButton');
        const done = setButtonBusy(button, 'Optimizando…');
        try {
            const segments = await window.SD_API.get(
                `${OPT_URL}/v1/optimization/optimal_route`,
                {
                    route_id: state.routeId,
                    day: state.day,
                    dist: params.dist
                }
            );
            const list = Array.isArray(segments) ? segments : (segments.data || []);
            state.segments = list;
            drawOptimizedRoute(list);
            renderSummary(list);
            setNote(`Ruta optimizada con ${list.length} segmento(s).`, 'success');
        } catch (error) {
            setNote(error.message || 'Error al optimizar.', 'error');
            toast(error.message || 'Error al optimizar.', 'error');
        } finally {
            hideLoader();
            done();
        }
    });
});
