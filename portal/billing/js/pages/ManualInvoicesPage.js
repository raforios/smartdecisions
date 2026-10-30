/**
 * ManualInvoicesPage — the paper invoices issued while the system was down,
 * transcribed and sent to the SIN.
 *
 * When the system itself cannot work (a software or hardware failure, or a
 * power cut), the shop issues the paper invoices it printed under a CAFC.
 * Once it is back, each paper invoice is transcribed here as it was written,
 * and the whole contingency is sent to the SIN within 72 hours.
 */
import {
    BillingService,
    PAYMENT_LABELS,
    SALE_PAYMENT_METHODS,
    errorText
} from '../services/BillingService.js';
import { escapeHtml, notify, setBusy, stamp } from '../ui.js';

/** The events of paper invoices, when the SIN's catalogue is not synced. */
const PAPER_EVENTS = new Map([
    ['5', 'Virus informático o falla de software'],
    ['6', 'Cambio de infraestructura o falla de hardware'],
    ['7', 'Corte de suministro de energía eléctrica']
]);

let cafcs = [];
let contingencies = [];
let events = PAPER_EVENTS;
let documentTypes = new Map();
let catalogue = [];

/**
 * A `datetime-local` value with the browser's offset, as the service wants it.
 *
 * @param {string} value "2026-10-27T10:00".
 * @returns {string} "2026-10-27T10:00:00-04:00".
 */
function withOffset(value) {
    const minutes = -new Date(value).getTimezoneOffset();
    const sign = minutes >= 0 ? '+' : '-';
    const hours = String(Math.floor(Math.abs(minutes) / 60)).padStart(2, '0');
    return `${value}:00${sign}${hours}:${String(Math.abs(minutes) % 60).padStart(2, '0')}`;
}

function options(map) {
    return [...map].map(([value, label]) =>
        `<option value="${escapeHtml(value)}">${escapeHtml(label)}</option>`).join('');
}

function renderCafcs(host) {
    host.querySelector('#cafc-body').innerHTML = cafcs.length
        ? cafcs.map((cafc) => `
            <tr><td><strong>${escapeHtml(cafc.cafc)}</strong></td>
                <td>${cafc.first_number} al ${cafc.last_number}</td>
                <td class="num">${cafc.used_numbers.length}</td></tr>`).join('')
        : '<tr class="empty"><td colspan="3">Todavía no registraste ningún CAFC.</td></tr>';
    host.querySelector('#open-cafc').innerHTML = options(new Map(
        cafcs.map((cafc) => [cafc.cafc, cafc.cafc])));
}

function renderContingencies(host) {
    host.querySelector('#manual-body').innerHTML = contingencies.length
        ? contingencies.map((one) => {
            const open = one.status === 'OPEN';
            return `
            <tr data-id="${escapeHtml(one.contingency_id)}">
                <td>${stamp(one.started_at)}</td><td>${stamp(one.ended_at)}</td>
                <td>${escapeHtml(events.get(String(one.event)) || one.event)}</td>
                <td>${escapeHtml(one.cafc)}</td>
                <td class="num">${one.sale_ids.length}</td>
                <td>${open ? '<span class="chip chip-warn">por enviar</span>'
                           : `<span class="chip">enviada · evento ${one.event_reception_code}</span>`}</td>
                <td>${open ? `<button class="btn btn-ghost btn-small transcribe">Transcribir</button>
                              <button class="btn btn-ghost btn-small send">Enviar al SIN</button>` : ''}</td>
            </tr>`;
        }).join('')
        : '<tr class="empty"><td colspan="7">No hay contingencias con facturas de papel.</td></tr>';
}

async function load(host) {
    try {
        [cafcs, contingencies] = await Promise.all([
            BillingService.listCafcs().then((page) => page.items),
            BillingService.listManualContingencies().then((page) => page.items)
        ]);
        renderCafcs(host);
        renderContingencies(host);
    } catch (error) {
        notify(errorText(error, 'No se pudieron leer las facturas manuales.'), 'error');
    }
}

function lineHtml() {
    return `
        <div class="field-row manual-line">
            <label class="field"><span>Código</span>
                <input type="text" class="line-sku" list="manual-skus" maxlength="40"></label>
            <label class="field"><span>Cantidad</span>
                <input type="number" class="line-qty" min="0" step="any"></label>
            <label class="field"><span>Precio unitario (Bs)</span>
                <input type="number" class="line-price" min="0" step="0.01"></label>
        </div>`;
}

function openTranscription(host, contingencyId) {
    const contingency = contingencies.find((one) => one.contingency_id === contingencyId);
    const panel = host.querySelector('#transcribe-panel');
    panel.dataset.id = contingencyId;
    host.querySelector('#transcribe-title').textContent =
        `Transcribir · CAFC ${contingency.cafc} · ${stamp(contingency.started_at)} a ${stamp(contingency.ended_at)}`;
    host.querySelector('#manual-lines').innerHTML = lineHtml();
    panel.hidden = false;
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function transcriptionBody(host) {
    const value = (id) => host.querySelector(id).value.trim();
    const method = value('#paper-method');
    return {
        number: Number(value('#paper-number')),
        issued_at: withOffset(value('#paper-issued')),
        buyer: {
            document: value('#paper-document'),
            document_type: Number(value('#paper-type')) || null,
            name: value('#paper-name') || null
        },
        lines: [...host.querySelectorAll('.manual-line')].map((row) => ({
            sku: row.querySelector('.line-sku').value.trim(),
            quantity: Number(row.querySelector('.line-qty').value),
            unit_price: Number(row.querySelector('.line-price').value)
        })).filter((line) => line.sku),
        payment_method: method,
        card_number: method.startsWith('TARJETA') ? value('#paper-card') || null : null
    };
}

function wireForms(host) {
    host.querySelector('#cafc-save').addEventListener('click', async (event) => {
        const done = setBusy(event.currentTarget, 'Guardando…');
        try {
            await BillingService.registerCafc({
                cafc: host.querySelector('#cafc-code').value.trim(),
                first_number: Number(host.querySelector('#cafc-first').value),
                last_number: Number(host.querySelector('#cafc-last').value)
            });
            notify('CAFC registrado.', 'success');
            await load(host);
        } catch (error) {
            notify(errorText(error, 'No se pudo registrar el CAFC.'), 'error');
        } finally {
            done();
        }
    });

    host.querySelector('#open-save').addEventListener('click', async (event) => {
        const done = setBusy(event.currentTarget, 'Abriendo…');
        try {
            await BillingService.openManualContingency({
                cafc: host.querySelector('#open-cafc').value,
                event: Number(host.querySelector('#open-event').value),
                started_at: withOffset(host.querySelector('#open-start').value),
                ended_at: withOffset(host.querySelector('#open-end').value)
            });
            notify('Contingencia abierta: ya puedes transcribir sus facturas.', 'success');
            await load(host);
        } catch (error) {
            notify(errorText(error, 'No se pudo abrir la contingencia.'), 'error');
        } finally {
            done();
        }
    });

    host.querySelector('#line-add').addEventListener('click', () => {
        host.querySelector('#manual-lines').insertAdjacentHTML('beforeend', lineHtml());
    });
    host.querySelector('#paper-method').addEventListener('change', (event) => {
        host.querySelector('#paper-card-field').hidden = !event.target.value.startsWith('TARJETA');
    });
    host.querySelector('#transcribe-back').addEventListener('click', () => {
        host.querySelector('#transcribe-panel').hidden = true;
    });
    host.querySelector('#transcribe-save').addEventListener('click', async (event) => {
        const panel = host.querySelector('#transcribe-panel');
        const done = setBusy(event.currentTarget, 'Transcribiendo…');
        try {
            const sale = await BillingService.transcribeInvoice(panel.dataset.id,
                                                                transcriptionBody(host));
            notify(`Factura ${sale.invoice.number} transcrita como la venta ${sale.number}.`,
                   'success');
            host.querySelector('#paper-number').value = '';
            host.querySelector('#manual-lines').innerHTML = lineHtml();
            await load(host);
        } catch (error) {
            notify(errorText(error, 'No se pudo transcribir la factura.'), 'error');
        } finally {
            done();
        }
    });

    host.querySelector('#manual-body').addEventListener('click', async (event) => {
        const row = event.target.closest('tr[data-id]');
        if (!row) return;
        if (event.target.classList.contains('transcribe')) {
            openTranscription(host, row.dataset.id);
            return;
        }
        if (!event.target.classList.contains('send')) return;
        const done = setBusy(event.target, '…');
        try {
            const outcome = await BillingService.sendManualContingency(row.dataset.id);
            if (!outcome.recovered) {
                notify('El SIN no responde todavía: vuelve a intentarlo en unos minutos.', 'error');
            } else {
                notify(`Enviadas ${outcome.invoices_sent} factura(s) al SIN`
                       + (outcome.invoices_observed
                           ? `; ${outcome.invoices_observed} observada(s), revísalas en Ventas.`
                           : '.'), outcome.invoices_observed ? 'error' : 'success');
            }
            host.querySelector('#transcribe-panel').hidden = true;
            await load(host);
        } catch (error) {
            notify(errorText(error, 'No se pudo enviar al SIN.'), 'error');
        } finally {
            done();
        }
    });
}

async function loadCatalogues() {
    const read = (name) => BillingService.siatCatalog(name)
        .then(({ entries }) => new Map(entries.map((entry) => [String(entry.code),
                                                               entry.description])))
        .catch(() => null);
    const [significant, documents, products] = await Promise.all([
        read('SIGNIFICANT_EVENTS'), read('IDENTITY_DOCUMENT_TYPES'),
        BillingService.listProducts({ only_active: true }).then((page) => page.items)
            .catch(() => [])
    ]);
    // Without the SIN's catalogue the three events keep their own names.
    if (significant) {
        events = new Map([...PAPER_EVENTS.keys()].map((code) =>
            [code, significant.get(code) || PAPER_EVENTS.get(code)]));
    }
    documentTypes = documents || new Map();
    catalogue = products;
}

/**
 * Paints the CAFCs and the manual contingencies, and wires the transcription.
 *
 * @param {HTMLElement} host Where the section mounts.
 */
export async function mountManualInvoices(host) {
    await loadCatalogues();
    host.innerHTML = `
        <header class="page-head">
            <h2>Facturas manuales</h2>
            <p class="muted">Cuando el sistema no puede funcionar (falla de software, de
               equipo o corte de luz), se emiten las facturas de papel impresas con un
               CAFC. Al volver, se transcriben aquí tal como se escribieron y se envían
               al SIN dentro de las 72 horas.</p>
        </header>

        <section class="card">
            <h3>CAFC</h3>
            <p class="muted small">El código que el SIN autorizó para tus facturas de
               contingencia, con el rango de números impresos.</p>
            <div class="table-scroll">
                <table class="data-table" data-no-pager>
                    <thead><tr><th>CAFC</th><th>Números</th><th class="num">Usados</th></tr></thead>
                    <tbody id="cafc-body"></tbody>
                </table>
            </div>
            <div class="field-row">
                <label class="field"><span>CAFC</span>
                    <input type="text" id="cafc-code" maxlength="50"></label>
                <label class="field"><span>Desde el número</span>
                    <input type="number" id="cafc-first" min="1" value="1"></label>
                <label class="field"><span>Hasta el número</span>
                    <input type="number" id="cafc-last" min="1" value="50"></label>
            </div>
            <div class="form-actions">
                <button class="btn btn-primary" id="cafc-save" type="button">Registrar CAFC</button>
            </div>
        </section>

        <section class="card">
            <h3>Contingencias con facturas de papel</h3>
            <div class="table-scroll">
                <table class="data-table">
                    <thead><tr><th>Inicio</th><th>Fin</th><th>Motivo</th><th>CAFC</th>
                        <th class="num">Facturas</th><th>Estado</th><th></th></tr></thead>
                    <tbody id="manual-body"></tbody>
                </table>
            </div>
            <h4>Nueva contingencia</h4>
            <div class="field-row">
                <label class="field"><span>CAFC</span><select id="open-cafc"></select></label>
                <label class="field"><span>Motivo</span>
                    <select id="open-event">${options(events)}</select></label>
                <label class="field"><span>Inicio</span>
                    <input type="datetime-local" id="open-start"></label>
                <label class="field"><span>Fin</span>
                    <input type="datetime-local" id="open-end"></label>
            </div>
            <div class="form-actions">
                <button class="btn btn-primary" id="open-save" type="button">Abrir contingencia</button>
            </div>
        </section>

        <section class="card" id="transcribe-panel" hidden>
            <h3 id="transcribe-title">Transcribir</h3>
            <p class="muted small">Copia la factura de papel tal como está escrita, con su
               número, fecha y precios. Descuenta stock y no entra en la caja.</p>
            <div class="field-row">
                <label class="field"><span>Número de la factura</span>
                    <input type="number" id="paper-number" min="1"></label>
                <label class="field"><span>Fecha y hora</span>
                    <input type="datetime-local" id="paper-issued"></label>
            </div>
            <div class="field-row">
                <label class="field"><span>Tipo de documento</span>
                    <select id="paper-type">${options(documentTypes)}</select></label>
                <label class="field"><span>NIT / CI</span>
                    <input type="text" id="paper-document" maxlength="40"></label>
                <label class="field"><span>Nombre o razón social</span>
                    <input type="text" id="paper-name" maxlength="200"></label>
            </div>
            <datalist id="manual-skus">${catalogue.map((product) =>
                `<option value="${escapeHtml(product.sku)}">${escapeHtml(product.description)}</option>`
            ).join('')}</datalist>
            <div id="manual-lines"></div>
            <div class="form-actions">
                <button class="btn btn-ghost btn-small" id="line-add" type="button">Agregar producto</button>
            </div>
            <div class="field-row">
                <label class="field"><span>Forma de pago</span>
                    <select id="paper-method">${options(new Map(SALE_PAYMENT_METHODS.map(
                        (method) => [method, PAYMENT_LABELS[method]])))}</select></label>
                <label class="field" id="paper-card-field" hidden><span>Número de tarjeta</span>
                    <input type="text" id="paper-card" maxlength="30"></label>
            </div>
            <div class="form-actions">
                <button class="btn btn-primary" id="transcribe-save" type="button">Transcribir factura</button>
                <button class="btn btn-ghost" id="transcribe-back" type="button">Volver</button>
            </div>
        </section>`;

    wireForms(host);
    await load(host);
}
