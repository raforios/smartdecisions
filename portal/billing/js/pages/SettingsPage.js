/**
 * SettingsPage — los datos del comercio y cómo numera sus notas.
 *
 * Es la primera pantalla de una instalación nueva: sin estos datos la nota no
 * tiene a quién pertenecer, y el backend se niega a emitir con
 * SETTINGS_NOT_FOUND.
 */
import { BillingService, errorText } from '../services/BillingService.js';
import { escapeHtml, notify, setBusy } from '../ui.js';

const WIDTHS = [['MM_80', '80 mm'], ['MM_58', '58 mm']];

/**
 * Pinta la configuración y la guarda.
 *
 * @param {HTMLElement} host Dónde se monta la sección.
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
            await BillingService.saveSettings({
                trade_name: tradeName,
                document: text('document'),
                address: text('address'),
                phone: text('phone'),
                ticket_footer: text('ticket_footer'),
                sale_series: host.querySelector('#sale_series').value.trim() || 'A',
                purchase_series: host.querySelector('#purchase_series').value.trim() || 'C',
                ticket_width: host.querySelector('#ticket_width').value,
                discounts_enabled: host.querySelector('#discounts_enabled').value === 'true'
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
