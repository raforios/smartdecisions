'use strict';

/**
 * Factores que cambian — the figures that move on their own (fuel, a tariff,
 * an index) and the local delivery cost built on two of them.
 *
 * QUOTES owns them. A factor is one figure and whether it counts; both carry
 * their date, and a calculation reads the state of ITS OWN day, so turning a
 * factor off today does not rewrite anything computed before. This screen only
 * declares, loads and reads: every rule lives in the service.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.isAuthenticated()) return;

    const { qs, toast, setButtonBusy } = window.SD_UI;
    const { errorText, money, shortDate, escapeHtml } = window.SD_MIN;
    const API = window.SD_API;
    const BASE = `${window.SD_CONFIG.QUOTES_URL}/v1/quotes/factors`;
    const ROWS_PER_PAGE = 10;
    const STATUS_LABELS = { ACTIVE: 'Activo', INACTIVE: 'Apagado' };

    const state = { factors: [], page: 0 };
    // The local day, not UTC: after 20:00 in Bolivia UTC is already tomorrow.
    const now = new Date();
    const today = [now.getFullYear(), String(now.getMonth() + 1).padStart(2, '0'),
                   String(now.getDate()).padStart(2, '0')].join('-');
    qs('#factorValueDate').value = today;
    qs('#transportDate').value = today;

    function note(selector, text, kind) {
        const element = qs(selector);
        element.textContent = text || '';
        element.classList.toggle('error', kind === 'error');
        element.classList.toggle('success', kind === 'success');
    }

    async function loadFactors() {
        try {
            const data = await API.get(BASE);
            state.factors = data.factors || [];
            qs('#factorsMeta').textContent = `${data.total} factor(es)`;
            note('#factorsNote', state.factors.length ? ''
                : 'Todavía no hay factores. Crea el primero abajo.');
            paintPage(state.page);
            paintSelect();
        } catch (error) {
            note('#factorsNote', errorText(error, 'No se pudieron leer los factores.'), 'error');
        }
    }

    // Ten rows per page and invisible filler on the last one, like every
    // table of the portal, so the card does not change height.
    function paintPage(page) {
        const factors = state.factors;
        const pages = Math.max(1, Math.ceil(factors.length / ROWS_PER_PAGE));
        state.page = Math.min(Math.max(page, 0), pages - 1);
        const shown = factors.slice(state.page * ROWS_PER_PAGE, (state.page + 1) * ROWS_PER_PAGE);

        const tbody = qs('#factorsTable tbody');
        tbody.innerHTML = shown.map((factor) => {
            const next = factor.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE';
            return `<tr><td><code>${escapeHtml(factor.code)}</code></td>` +
                `<td>${escapeHtml(factor.name)}</td>` +
                `<td>${escapeHtml(factor.unit)}</td>` +
                `<td class="num">${factor.latest_value == null ? '—' : money(factor.latest_value)}</td>` +
                `<td>${factor.latest_date ? shortDate(factor.latest_date) : '—'}</td>` +
                `<td>${STATUS_LABELS[factor.status] || factor.status}</td>` +
                `<td><button type="button" class="btn btn-ghost btn-small" ` +
                `data-toggle="${escapeHtml(factor.code)}" data-next="${next}">` +
                `${next === 'ACTIVE' ? 'Encender' : 'Apagar'}</button></td></tr>`;
        }).join('');
        if (factors.length > ROWS_PER_PAGE) {
            tbody.innerHTML += '<tr class="row-filler"><td colspan="7">&nbsp;</td></tr>'
                .repeat(ROWS_PER_PAGE - shown.length);
        }
        qs('#factorsCount').textContent = `${factors.length} factor(es)`;
        qs('#factorsPage').textContent = `${state.page + 1} / ${pages}`;
        qs('#factorsPrev').disabled = state.page === 0;
        qs('#factorsNext').disabled = state.page >= pages - 1;
        qs('#factorsPager').hidden = factors.length <= ROWS_PER_PAGE;
    }

    function paintSelect() {
        const select = qs('#factorValueCode');
        const chosen = select.value;
        select.innerHTML = state.factors
            .map((factor) => `<option value="${escapeHtml(factor.code)}">` +
                `${escapeHtml(factor.code)} · ${escapeHtml(factor.name)}</option>`)
            .join('');
        if (chosen) select.value = chosen;
    }

    /**
     * Turning a factor on or off is declaring it again with the other status,
     * from today: the service keeps its readings and the dated history of the
     * switch, which is what lets a past report be reproduced.
     */
    qs('#factorsTable').addEventListener('click', async (event) => {
        const button = event.target.closest('[data-toggle]');
        if (!button) return;
        const factor = state.factors.find((item) => item.code === button.dataset.toggle);
        if (!factor) return;
        const done = setButtonBusy(button, '…');
        try {
            await API.post(BASE, {
                code: factor.code, name: factor.name, unit: factor.unit,
                source: factor.source || null, status: button.dataset.next,
                effective_from: today
            });
            toast(button.dataset.next === 'ACTIVE' ? 'Factor encendido.' : 'Factor apagado.',
                  'success');
            await loadFactors();
        } catch (error) {
            note('#factorsNote', errorText(error, 'No se pudo cambiar el estado.'), 'error');
        } finally {
            done();
        }
    });

    qs('#factorCreateButton').addEventListener('click', async () => {
        const code = qs('#factorCode').value.trim().toUpperCase();
        const name = qs('#factorName').value.trim();
        const unit = qs('#factorUnit').value.trim();
        if (!code || !name || !unit) {
            note('#factorFormNote', 'Código, nombre y unidad son obligatorios.', 'error');
            return;
        }
        const done = setButtonBusy(qs('#factorCreateButton'), 'Creando…');
        try {
            await API.post(BASE, {
                code, name, unit, source: qs('#factorSource').value.trim() || null
            });
            note('#factorFormNote', `Factor ${code} creado. Ya puedes cargarle valores.`,
                 'success');
            ['#factorCode', '#factorName', '#factorUnit', '#factorSource']
                .forEach((selector) => { qs(selector).value = ''; });
            await loadFactors();
            qs('#factorValueCode').value = code;
        } catch (error) {
            note('#factorFormNote', errorText(error, 'No se pudo crear el factor.'), 'error');
        } finally {
            done();
        }
    });

    qs('#factorValueButton').addEventListener('click', async () => {
        const code = qs('#factorValueCode').value;
        const day = qs('#factorValueDate').value;
        const raw = qs('#factorValue').value;
        if (!code || !day || raw === '') {
            note('#factorFormNote', 'Elige el factor, la fecha y el valor.', 'error');
            return;
        }
        const done = setButtonBusy(qs('#factorValueButton'), 'Guardando…');
        try {
            await API.post(`${BASE}/${encodeURIComponent(code)}/values`, {
                values: [{ factor_date: day, value: Number(raw) }]
            });
            note('#factorFormNote', `Valor de ${code} guardado para el ${shortDate(day)}.`,
                 'success');
            qs('#factorValue').value = '';
            await loadFactors();
        } catch (error) {
            note('#factorFormNote', errorText(error, 'No se pudo guardar el valor.'), 'error');
        } finally {
            done();
        }
    });

    /** The whole chain, not only the total: each step can be checked by hand. */
    qs('#transportButton').addEventListener('click', async () => {
        const km = qs('#transportKm').value;
        const day = qs('#transportDate').value;
        const units = qs('#transportUnits').value;
        const box = qs('#transportResult');
        if (!km || Number(km) <= 0 || !day) {
            box.innerHTML = '<p class="control-hint error">Indica los km y la fecha.</p>';
            return;
        }
        const done = setButtonBusy(qs('#transportButton'), 'Calculando…');
        try {
            const params = { km, date: day };
            if (units) params.units = units;
            const cost = await API.get(`${BASE}/transport-cost`, params);
            const rows = [
                ['Recorrido (ida)', `${money(cost.distance_km)} km`],
                ['Viaje redondo', `${money(cost.round_trip_km)} km`],
                ['Rendimiento', `${money(cost.kilometres_per_litre)} km por litro`],
                ['Litros', money(cost.litres)],
                ['Precio del litro', money(cost.price_per_litre)],
                ['Costo del recorrido', money(cost.cost)]
            ];
            if (cost.cost_per_unit != null) {
                rows.push(['Costo por unidad', money(cost.cost_per_unit)]);
            }
            box.innerHTML = '<table class="data-table"><tbody>' +
                rows.map(([label, value]) =>
                    `<tr><td>${label}</td><td class="num">${value}</td></tr>`).join('') +
                '</tbody></table>' +
                `<p class="control-hint">Valores vigentes al ${shortDate(cost.as_of)}.</p>`;
        } catch (error) {
            box.innerHTML = `<p class="control-hint error">${escapeHtml(
                errorText(error, 'No se pudo calcular el costo.'))}</p>`;
        } finally {
            done();
        }
    });

    qs('#factorsPrev').addEventListener('click', () => paintPage(state.page - 1));
    qs('#factorsNext').addEventListener('click', () => paintPage(state.page + 1));

    loadFactors();
});
