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
        // Un comercio recién instalado todavía no tiene parámetros: eso no es
        // un fallo, es el estado inicial.
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
                <p class="muted small">
                    Estos datos forman parte del CUF de cada factura. Déjalos en
                    cero mientras no tengas la autorización del SIN.
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

    host.querySelector('#save').addEventListener('click', async (event) => {
        const tradeName = host.querySelector('#trade_name').value.trim();
        if (!tradeName) {
            notify('El nombre comercial es obligatorio: se imprime en cada nota.', 'error');
            return;
        }
        const done = setBusy(event.currentTarget, 'Guardando…');
        const text = (id) => host.querySelector(`#${id}`).value.trim() || null;
        try {
            // The record is saved whole: what this form does not show
            // (the invoice municipality, for example) is kept as it is.
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
