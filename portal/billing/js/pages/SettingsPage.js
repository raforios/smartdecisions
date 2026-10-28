/**
 * SettingsPage — the merchant's data and how it numbers its notes.
 *
 * It is the first screen of a new installation: without this data the note has
 * nobody to belong to, and the backend refuses to issue with
 * SETTINGS_NOT_FOUND.
 */
import { BillingService, errorText } from '../services/BillingService.js';
import { escapeHtml, notify, setBusy } from '../ui.js';

const WIDTHS = [['MM_80', '80 mm'], ['MM_58', '58 mm']];

/** The events this system issues offline: the first four of the SIN's catalogue. */
const OFFLINE_EVENTS = ['1', '2', '3', '4'];

async function paintContingency(host) {
    const state = host.querySelector('#contingency-state');
    try {
        const status = await BillingService.contingency();
        state.textContent = status.offline
            ? `Fuera de línea desde ${status.contingency.started_at.replace('T', ' ').slice(0, 16)}`
              + ` · ${status.contingency.pending_invoices} factura(s) esperan su envío.`
              + ' El sistema reintenta solo.'
            : 'En línea: cada factura se envía al SIN en el momento.';
        host.querySelector('#contingency-start').disabled = status.offline;
        host.querySelector('#contingency-recover').disabled = !status.offline;
    } catch (error) {
        state.textContent = errorText(error, 'No se pudo leer la conexión con el SIN.');
    }
}

async function wireContingency(host) {
    try {
        const { entries } = await BillingService.siatCatalog('SIGNIFICANT_EVENTS');
        host.querySelector('#contingency-event').innerHTML = entries
            .filter((entry) => OFFLINE_EVENTS.includes(entry.code))
            .map((entry) => `<option value="${escapeHtml(entry.code)}">${
                escapeHtml(entry.description)}</option>`).join('');
    } catch (error) {
        // Without the catalogue there is nothing to choose; the status still shows.
        if (error.code !== 'CATALOG_NOT_SYNCED') {
            notify(errorText(error, 'No se pudieron leer los eventos del SIN.'), 'error');
        }
    }
    host.querySelector('#contingency-start').addEventListener('click', async (event) => {
        const done = setBusy(event.currentTarget, 'Pasando…');
        try {
            await BillingService.startContingency(
                Number(host.querySelector('#contingency-event').value));
            notify('Las facturas se emiten fuera de línea desde ahora.', 'success');
        } catch (error) {
            notify(errorText(error, 'No se pudo pasar a fuera de línea.'), 'error');
        } finally {
            done();
            await paintContingency(host);
        }
    });
    host.querySelector('#contingency-recover').addEventListener('click', async (event) => {
        const done = setBusy(event.currentTarget, 'Reintentando…');
        try {
            const result = await BillingService.recoverContingency();
            notify(result.recovered
                ? `Conexión recuperada: ${result.invoices_sent} factura(s) enviadas al SIN.`
                : 'El SIN todavía no responde; el sistema seguirá reintentando.',
                result.recovered ? 'success' : 'info');
        } catch (error) {
            notify(errorText(error, 'No se pudo reintentar.'), 'error');
        } finally {
            done();
            await paintContingency(host);
        }
    });
    await paintContingency(host);
}

/**
 * Paints the settings and saves them.
 *
 * @param {HTMLElement} host Where the section mounts.
 */
export async function mountSettings(host) {
    let settings = null;
    try {
        settings = await BillingService.getSettings();
    } catch (error) {
        // A freshly installed shop has no settings yet: that is not a failure,
        // it is where it starts.
        if (error.code !== 'SETTINGS_NOT_FOUND') throw error;
    }

    const value = (field, fallback = '') => escapeHtml(settings?.[field] ?? fallback);

    host.innerHTML = `
        <header class="page-head">
            <h2>Configuración</h2>
            <p class="muted">Lo que se imprime en cada nota y cómo se numeran.</p>
        </header>

        <div class="panel-grid">
            <section class="card">
                <h3>El comercio</h3>
                <label class="field">
                    <span>Nombre comercial</span>
                    <input type="text" id="trade_name" maxlength="200"
                           value="${value('trade_name')}" required>
                </label>
                <div class="field-row">
                    <label class="field">
                        <span>NIT</span>
                        <input type="text" id="document" maxlength="40" value="${value('document')}">
                    </label>
                    <label class="field">
                        <span>Teléfono</span>
                        <input type="text" id="phone" maxlength="40" value="${value('phone')}">
                    </label>
                </div>
                <label class="field">
                    <span>Dirección</span>
                    <input type="text" id="address" maxlength="300" value="${value('address')}">
                </label>
                <label class="field">
                    <span>Pie de la nota</span>
                    <input type="text" id="ticket_footer" maxlength="200"
                           placeholder="¡Gracias por su compra!"
                           value="${value('ticket_footer')}">
                </label>
            </section>

            <section class="card">
                <h3>Notas y mostrador</h3>
                <div class="field-row">
                    <label class="field">
                        <span>Serie de venta</span>
                        <input type="text" id="sale_series" maxlength="8"
                               value="${value('sale_series', 'A')}">
                    </label>
                    <label class="field">
                        <span>Serie de compra</span>
                        <input type="text" id="purchase_series" maxlength="8"
                               value="${value('purchase_series', 'C')}">
                    </label>
                </div>
                <label class="field">
                    <span>Ancho del papel</span>
                    <select id="ticket_width">
                        ${WIDTHS.map(([code, label]) => `
                            <option value="${code}"
                                ${settings?.ticket_width === code ? 'selected' : ''}>
                                ${label}
                            </option>`).join('')}
                    </select>
                </label>
                <label class="field">
                    <span>Descuentos por línea</span>
                    <select id="discounts_enabled">
                        <option value="false" ${settings?.discounts_enabled ? '' : 'selected'}>
                            Desactivados
                        </option>
                        <option value="true" ${settings?.discounts_enabled ? 'selected' : ''}>
                            Activados
                        </option>
                    </select>
                </label>

                ${settings ? `
                    <p class="muted small">
                        Próxima nota de venta: <strong>${settings.sale_series}-${
                            String(settings.next_sale_number).padStart(6, '0')}</strong> ·
                        próxima compra: <strong>${settings.purchase_series}-${
                            String(settings.next_purchase_number).padStart(6, '0')}</strong>.
                        La numeración no se reinicia al cambiar el nombre.
                    </p>` : `
                    <p class="muted small">
                        Todavía no guardaste la configuración: hasta hacerlo, el
                        mostrador no puede emitir notas.
                    </p>`}

            </section>

            <!-- Branch and point of sale go INSIDE the CUF, so they belong to
                 the pharmacy and not to the service. Nominativity is a flag
                 because a pharmacy that still issues internal notes has to
                 keep selling until it is authorized. -->
            <section class="card">
                <h3>Facturación electrónica</h3>
                <label class="field">
                    <span>Emitir factura en cada venta</span>
                    <select id="invoicing_enabled">
                        <option value="false" ${settings?.invoicing_enabled ? '' : 'selected'}>
                            No — nota de venta interna
                        </option>
                        <option value="true" ${settings?.invoicing_enabled ? 'selected' : ''}>
                            Sí — cada venta se envía al SIN como factura
                        </option>
                    </select>
                </label>
                <p class="muted small">
                    Al activarlo, toda venta pide el documento del comprador y su
                    tipo, y cada producto necesita sus códigos del SIN. Si el SIN
                    rechaza la factura o no responde, la venta no se registra.
                </p>
                <label class="field">
                    <span>Municipio</span>
                    <input type="text" id="municipality" maxlength="25"
                           placeholder="La Paz" value="${value('municipality')}">
                </label>
                <p class="muted small">
                    Sucursal y punto de venta forman parte del CUF de cada factura:
                    deben ser los que registraste en el SIN.
                </p>
                <div class="form-actions">
                    <button class="btn btn-secondary" id="sync-catalogs" type="button">
                        Sincronizar catálogos del SIN
                    </button>
                </div>
                <!-- Contingency: the system enters it alone when the SIN does not
                     answer, and leaves it alone; by hand only when the shop knows
                     first, like a point of sale with no internet. -->
                <h4>Conexión con el SIN</h4>
                <p class="muted small" id="contingency-state">Consultando…</p>
                <div class="field-row">
                    <label class="field">
                        <span>Motivo para emitir fuera de línea</span>
                        <select id="contingency-event"></select>
                    </label>
                </div>
                <div class="form-actions">
                    <button class="btn btn-secondary" id="contingency-start" type="button">
                        Emitir fuera de línea
                    </button>
                    <button class="btn btn-secondary" id="contingency-recover" type="button">
                        Reintentar envío ahora
                    </button>
                </div>
                <p class="muted small">
                    Trae del SIN las leyendas, los tipos de documento, las unidades y
                    los productos de tu actividad. Hazlo antes de la primera factura
                    y cuando el SIN anuncie cambios.
                </p>
                <div class="field-row">
                    <label class="field">
                        <span>Sucursal</span>
                        <input type="number" id="branch" min="0" max="9999"
                               value="${value('branch', 0)}">
                    </label>
                    <label class="field">
                        <span>Punto de venta</span>
                        <input type="number" id="point_of_sale" min="0" max="9999"
                               value="${value('point_of_sale', 0)}">
                    </label>
                </div>
                <label class="field">
                    <span>Hora de alerta de cierre de caja</span>
                    <input type="time" id="cash_alert_time"
                           value="${value('cash_alert_time').slice(0, 5)}">
                </label>
                <p class="muted small">
                    Desde esta hora, el sistema avisa qué cajas siguen abiertas. Cada
                    caja es de un día: la que quede abierta no deja vender al día
                    siguiente hasta cerrarla.
                </p>
                <label class="field">
                    <span>Exigir documento del comprador</span>
                    <select id="buyer_required">
                        <option value="false" ${settings?.buyer_required ? '' : 'selected'}>
                            No — se puede vender al mostrador
                        </option>
                        <option value="true" ${settings?.buyer_required ? 'selected' : ''}>
                            Sí — obligatorio en toda venta
                        </option>
                    </select>
                </label>
                <p class="muted small">
                    Al facturar electrónicamente es obligatorio: la norma exige el
                    <strong>número de documento</strong> en toda factura, sin importar
                    el monto. El nombre no es obligatorio.
                </p>

                <button class="btn btn-primary btn-block" id="save">Guardar</button>
            </section>
        </div>`;

    wireContingency(host);

    host.querySelector('#sync-catalogs').addEventListener('click', async (event) => {
        const done = setBusy(event.currentTarget, 'Sincronizando…');
        try {
            const { catalogs } = await BillingService.syncSiatCatalogs();
            notify(`${catalogs.length} catálogos del SIN sincronizados.`, 'success');
        } catch (error) {
            notify(errorText(error, 'No se pudieron sincronizar los catálogos.'), 'error');
        } finally {
            done();
        }
    });

    host.querySelector('#save').addEventListener('click', async (event) => {
        const tradeName = host.querySelector('#trade_name').value.trim();
        if (!tradeName) {
            notify('El nombre comercial es obligatorio: se imprime en cada nota.', 'error');
            return;
        }
        const done = setBusy(event.currentTarget, 'Guardando…');
        const text = (id) => host.querySelector(`#${id}`).value.trim() || null;
        try {
            // The record is saved whole: what this form does not show is kept
            // as it is.
            const { next_sale_number: _sale, next_purchase_number: _purchase, ...kept } =
                settings || {};
            await BillingService.saveSettings({
                ...kept,
                trade_name: tradeName,
                document: text('document'),
                address: text('address'),
                phone: text('phone'),
                ticket_footer: text('ticket_footer'),
                sale_series: host.querySelector('#sale_series').value.trim() || 'A',
                purchase_series: host.querySelector('#purchase_series').value.trim() || 'C',
                ticket_width: host.querySelector('#ticket_width').value,
                discounts_enabled: host.querySelector('#discounts_enabled').value === 'true',
                branch: Number(host.querySelector('#branch').value) || 0,
                point_of_sale: Number(host.querySelector('#point_of_sale').value) || 0,
                buyer_required: host.querySelector('#buyer_required').value === 'true',
                invoicing_enabled: host.querySelector('#invoicing_enabled').value === 'true',
                municipality: text('municipality'),
                cash_alert_time: host.querySelector('#cash_alert_time').value || null
            });
            document.getElementById('shopName').textContent = tradeName;
            notify('Configuración guardada.', 'success');
            await mountSettings(host);
        } catch (error) {
            notify(errorText(error, 'No se pudo guardar.'), 'error');
        } finally {
            done();
        }
    });
}
