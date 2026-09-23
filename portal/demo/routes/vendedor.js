'use strict';

/**
 * Mi ruta — the seller's phone screen.
 *
 * One day, one route: pick today's plan (or go free), start where you stand,
 * register each visit with what came of it and what you sold, close at the
 * end. The stock of the day comes down with every sale, so a product that
 * ran out is refused on the spot instead of promised.
 *
 * The service pins `seller` to the caller's email for a SELLER; a manager
 * opening this screen runs it as themselves, which is fine for a trial.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.requireAuth()) return;
    const { qs, toast, setButtonBusy } = window.SD_UI;
    const T = window.SD_TRACK;
    const GEOFENCE = window.SD_CONFIG.GEOFENCE_METERS;
    const me = window.SD_AUTH.getEmail();

    qs('#userChip').textContent = me || 'vendedor';
    qs('#logoutButton').addEventListener('click', () => window.SD_AUTH.logout());
    window.SD_SESSION.mountChip('sessionChip', 'La ruta abierta sigue en el servidor aunque la sesión venza.');
    qs('#dayLine').textContent = new Date().toLocaleDateString('es-BO', {
        weekday: 'long', day: 'numeric', month: 'long'
    });

    const state = { plans: [], plan: null, route: null, stock: [], visiting: null };

    // ---------- geolocation ----------
    const MAX_ACCURACY = window.SD_CONFIG.GPS_MAX_ACCURACY_METERS;

    /**
     * A fresh, precise fix or nothing. The device says how good the reading
     * is; a laptop located by Wi-Fi/IP reports hundreds or thousands of metres
     * and would register the visit kilometres away, so it is refused with the
     * figure, not silently accepted.
     */
    function locate() {
        return new Promise((resolve, reject) => {
            if (!navigator.geolocation) {
                reject(new Error('Este dispositivo no permite leer la ubicación.'));
                return;
            }
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    const { latitude, longitude, accuracy } = position.coords;
                    showPosition(latitude, longitude, accuracy);
                    if (accuracy > MAX_ACCURACY) {
                        reject(new Error(
                            `Ubicación imprecisa (±${Math.round(accuracy)} m). Activa el GPS del ` +
                            `teléfono y sal a cielo abierto; se aceptan lecturas de hasta ${MAX_ACCURACY} m.`
                        ));
                        return;
                    }
                    resolve({ lat: latitude, lon: longitude, accuracy });
                },
                () => reject(new Error('No se pudo leer la ubicación. Activa el GPS y permite el acceso.')),
                { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
            );
        });
    }

    function showPosition(lat, lon, accuracy) {
        const line = qs('#positionLine');
        line.hidden = false;
        line.textContent = `Tu posición: ${lat.toFixed(6)}, ${lon.toFixed(6)} (±${Math.round(accuracy)} m)`;
        line.classList.toggle('is-poor', accuracy > MAX_ACCURACY);
    }

    // ---------- load ----------
    async function load() {
        const today = T.todayIso();
        try {
            const [plans, routes, stock] = await Promise.all([
                T.planned.filter({ route_status: 'ACTIVE' }),
                T.executed.list({ date_from: today, date_to: today }),
                T.stock.day(today).catch(() => ({ items: [] }))
            ]);
            // My plans first (assigned by email); unassigned ones stay selectable.
            state.plans = plans.filter((plan) => !plan.seller || plan.seller === me)
                .sort((a, b) => (a.seller === me ? -1 : 1) - (b.seller === me ? -1 : 1));
            state.stock = stock.items || [];
            const mine = routes.filter((route) => route.seller === me);
            const open = mine.find((route) => !route.end_time);
            if (open) {
                state.route = await T.executed.get(open.id);
                state.plan = state.route.planned_route_id
                    ? plans.find((plan) => plan.id === state.route.planned_route_id) || null : null;
                showRoute();
            } else if (mine.length) {
                state.route = mine[mine.length - 1];
                showClosed();
            } else {
                showStart();
            }
        } catch (error) {
            toast(T.errorText(error, 'No se pudo cargar tu día.'), 'error');
        }
    }

    // ---------- start ----------
    function showStart() {
        qs('#routePanel').hidden = true;
        qs('#closedCard').hidden = true;
        qs('#startCard').hidden = false;
        const select = qs('#planSelect');
        select.innerHTML = '<option value="">Sin plan (ruta libre)</option>';
        state.plans.forEach((plan) => {
            const option = document.createElement('option');
            option.value = plan.id;
            option.textContent = `${plan.route_name} · ${plan.points.length} paradas` +
                (plan.seller === me ? ' · asignado a ti' : '');
            select.appendChild(option);
        });
        const mine = state.plans.find((plan) => plan.seller === me);
        if (mine) select.value = mine.id;
        describePlan();
    }
    function describePlan() {
        const plan = state.plans.find((item) => item.id === qs('#planSelect').value);
        qs('#planHint').textContent = plan
            ? `Empieza en ${plan.points[0].point_name}. Debes estar a menos de ${GEOFENCE} m para iniciar.`
            : 'Sin plan, la ruta se arma con lo que visites; gerencia puede convertirla en plan después.';
    }
    qs('#planSelect').addEventListener('change', describePlan);

    qs('#startButton').addEventListener('click', async () => {
        const done = setButtonBusy(qs('#startButton'), 'Ubicando…');
        T.note(qs('#startNote'), '');
        try {
            const here = await locate();
            const planId = qs('#planSelect').value || null;
            const route = await T.executed.start({
                seller: me, start_time: T.nowIso(), planned_route_id: planId,
                start_latitude: here.lat, start_longitude: here.lon, max_distance_start_point: GEOFENCE
            });
            state.route = await T.executed.get(route.id);
            state.plan = state.plans.find((plan) => plan.id === planId) || null;
            toast('Ruta iniciada. Buen día de ventas.', 'success');
            showRoute();
        } catch (error) {
            T.note(qs('#startNote'), T.errorText(error, 'No se pudo iniciar la ruta.'), 'error');
        } finally {
            done();
        }
    });

    // ---------- open route ----------
    function showRoute() {
        qs('#startCard').hidden = true;
        qs('#closedCard').hidden = true;
        qs('#routePanel').hidden = false;
        paintSummary();
        paintStops();
        hideVisit();
    }
    function visitsByClient() {
        const seen = {};
        (state.route.points || []).forEach((point) => {
            if (point.client_id) seen[point.client_id] = point;
        });
        return seen;
    }
    function paintSummary() {
        const points = state.route.points || [];
        const visits = points.filter((point) => point.client_id).length;
        const sales = points.filter((point) => point.outcome === 'VENTA').length;
        const planned = state.plan ? state.plan.points.length : 0;
        qs('#routeSummary').innerHTML =
            metric('Desde', T.formatStamp(state.route.start_time)) +
            metric('Visitas', planned ? `${visits} / ${planned}` : String(visits)) +
            metric('Ventas', String(sales));
    }
    function paintStops() {
        const list = qs('#stopList');
        list.innerHTML = '';
        qs('#stopsTitle').textContent = state.plan ? `Paradas · ${state.plan.route_name}` : 'Visitas de hoy';
        const done = visitsByClient();
        if (state.plan) {
            state.plan.points.forEach((stop) => {
                const visit = stop.client_id ? done[stop.client_id] : null;
                const row = document.createElement('div');
                row.className = 'seller-stop' + (visit ? ' is-done' : '');
                row.innerHTML =
                    `<span class="stop-pin" style="background:${visit ? T.PIN_COLORS.sale : T.PIN_COLORS.plan}">${stop.secuencial}</span>` +
                    `<span class="seller-stop-name">${T.escapeHtml(stop.point_name)}` +
                    (visit ? `<small>${T.escapeHtml(T.OUTCOME_LABELS[visit.outcome] || 'visitado')} · ${T.escapeHtml(T.formatStamp(visit.timestamp))}</small>` : '') +
                    '</span>' +
                    (visit ? '' : `<button type="button" class="btn btn-primary btn-small" data-client="${T.escapeHtml(stop.client_id || stop.point_name)}">Visitar</button>`);
                list.appendChild(row);
            });
        } else {
            (state.route.points || []).filter((point) => point.client_id).forEach((point, index) => {
                const row = document.createElement('div');
                row.className = 'seller-stop is-done';
                row.innerHTML =
                    `<span class="stop-pin" style="background:${point.outcome === 'VENTA' ? T.PIN_COLORS.sale : T.PIN_COLORS.point}">${index + 1}</span>` +
                    `<span class="seller-stop-name">${T.escapeHtml(point.client_id)}` +
                    `<small>${T.escapeHtml(T.OUTCOME_LABELS[point.outcome] || 'visitado')} · ${T.escapeHtml(T.formatStamp(point.timestamp))}</small></span>`;
                list.appendChild(row);
            });
            if (!list.children.length) list.innerHTML = '<p class="legend-hint">Todavía no registraste visitas.</p>';
        }
    }
    qs('#stopList').addEventListener('click', (event) => {
        const button = event.target.closest('[data-client]');
        if (button) openVisit(button.dataset.client);
    });
    qs('#freeVisitButton').addEventListener('click', () => openVisit(''));

    // ---------- visit form ----------
    function openVisit(client) {
        state.visiting = client;
        qs('#visitTitle').textContent = client ? `Visita a ${client}` : 'Visita fuera del plan';
        qs('#visitClient').value = client;
        qs('#visitOutcome').value = 'VENTA';
        qs('#visitOrder').value = '';
        qs('#itemRows').innerHTML = '';
        addItemRow();
        toggleSaleFields();
        T.note(qs('#visitNote'), '');
        qs('#stockHint').textContent = state.stock.length
            ? `Stock de hoy: ${state.stock.map((item) => `${item.sku} ${T.formatQuantity(item.available_quantity)}`).join(' · ')}`
            : 'Hoy no hay stock cargado; las ventas no se descuentan.';
        qs('#visitCard').hidden = false;
        qs('#visitCard').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    function hideVisit() { qs('#visitCard').hidden = true; state.visiting = null; }
    function toggleSaleFields() {
        const selling = qs('#visitOutcome').value === 'VENTA';
        qs('#orderField').hidden = !selling;
        qs('#itemsField').hidden = !selling;
    }
    qs('#visitOutcome').addEventListener('change', toggleSaleFields);
    qs('#visitCancelButton').addEventListener('click', hideVisit);

    function addItemRow() {
        const row = document.createElement('div');
        row.className = 'seller-item-row';
        const options = state.stock.map((item) =>
            `<option value="${T.escapeHtml(item.sku)}">${T.escapeHtml(item.sku)}${item.product_name ? ` · ${T.escapeHtml(item.product_name)}` : ''}</option>`
        ).join('');
        row.innerHTML = state.stock.length
            ? `<select class="item-sku">${options}</select>`
            : '<input type="text" class="item-sku" placeholder="SKU" maxlength="64">';
        row.innerHTML += '<input type="number" class="item-qty" min="0.01" step="any" placeholder="Cant.">' +
            '<button type="button" class="btn btn-ghost btn-small" data-remove>×</button>';
        qs('#itemRows').appendChild(row);
    }
    qs('#addItemButton').addEventListener('click', addItemRow);
    qs('#itemRows').addEventListener('click', (event) => {
        const button = event.target.closest('[data-remove]');
        if (button) button.closest('.seller-item-row').remove();
    });
    function readItems() {
        return [...qs('#itemRows').querySelectorAll('.seller-item-row')].map((row) => ({
            sku: row.querySelector('.item-sku').value.trim(),
            quantity: Number(row.querySelector('.item-qty').value)
        })).filter((item) => item.sku && item.quantity > 0);
    }

    qs('#visitSaveButton').addEventListener('click', async () => {
        const client = qs('#visitClient').value.trim();
        if (!client) { T.note(qs('#visitNote'), 'Indica el cliente.', 'error'); return; }
        const outcome = qs('#visitOutcome').value;
        const items = outcome === 'VENTA' ? readItems() : [];
        const done = setButtonBusy(qs('#visitSaveButton'), 'Guardando…');
        try {
            const here = await locate();
            await T.executed.report({
                executed_route_id: state.route.id, timestamp: T.nowIso(),
                latitude: here.lat, longitude: here.lon,
                client_id: client, outcome,
                order_id: outcome === 'VENTA' ? (qs('#visitOrder').value.trim() || null) : null,
                items
            });
            toast(outcome === 'VENTA' ? 'Venta registrada.' : 'Visita registrada.', 'success');
            await refreshRoute();
            hideVisit();
        } catch (error) {
            T.note(qs('#visitNote'), T.errorText(error, 'No se pudo registrar la visita.'), 'error');
        } finally {
            done();
        }
    });

    async function refreshRoute() {
        state.route = await T.executed.get(state.route.id);
        try { state.stock = (await T.stock.day(T.todayIso())).items || []; } catch (_) { /* keep the last list */ }
        paintSummary();
        paintStops();
    }

    // ---------- position / close / reopen ----------
    qs('#pingButton').addEventListener('click', async () => {
        const done = setButtonBusy(qs('#pingButton'), 'Ubicando…');
        try {
            const here = await locate();
            await T.executed.report({
                executed_route_id: state.route.id, timestamp: T.nowIso(),
                latitude: here.lat, longitude: here.lon
            });
            toast('Posición enviada.', 'success');
        } catch (error) {
            toast(T.errorText(error, 'No se pudo enviar la posición.'), 'error');
        } finally {
            done();
        }
    });

    qs('#closeButton').addEventListener('click', async () => {
        const done = setButtonBusy(qs('#closeButton'), 'Cerrando…');
        T.note(qs('#closeNote'), '');
        try {
            const here = await locate();
            state.route = await T.executed.close(state.route.id, {
                end_time: T.nowIso(), end_latitude: here.lat, end_longitude: here.lon,
                max_distance_end_point: GEOFENCE
            });
            toast('Ruta cerrada.', 'success');
            showClosed();
        } catch (error) {
            T.note(qs('#closeNote'), T.errorText(error, 'No se pudo cerrar la ruta.'), 'error');
        } finally {
            done();
        }
    });

    function showClosed() {
        qs('#startCard').hidden = true;
        qs('#routePanel').hidden = true;
        qs('#closedCard').hidden = false;
        qs('#closedLine').textContent =
            `Empezó ${T.formatStamp(state.route.start_time)} y cerró ${T.formatStamp(state.route.end_time)} ` +
            `con ${state.route.points_count} punto(s) reportados.`;
    }
    qs('#reopenButton').addEventListener('click', async () => {
        T.note(qs('#reopenNote'), '');
        try {
            await T.executed.reopen(state.route.id);
            state.route = await T.executed.get(state.route.id);
            toast('Ruta reabierta.', 'success');
            showRoute();
        } catch (error) {
            T.note(qs('#reopenNote'), T.errorText(error, 'No se pudo reabrir.'), 'error');
        }
    });
    qs('#newRouteButton').addEventListener('click', showStart);

    function metric(label, value) {
        return `<div class="metric"><p class="metric-label">${T.escapeHtml(label)}</p>` +
               `<p class="metric-value">${T.escapeHtml(value)}</p></div>`;
    }

    load();
});
