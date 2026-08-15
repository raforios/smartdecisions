/**
 * Printable warehouse forms (FORMULARIOS.PDF).
 *
 * Two documents are signed on paper for every request:
 *   - FORMULARIO - SOLICITUD DE ALMACENES: what the user asked for.
 *   - FORMULARIO - ENTREGA DE ALMACENES: what the warehouse handed over,
 *     with requested and delivered quantities side by side.
 *
 * Both are rendered as a standalone HTML document and sent to the browser's
 * print dialog. Keeping the layout here (instead of generating a PDF on the
 * server) avoids shipping a PDF library inside the Lambda bundle, and the
 * browser's "Save as PDF" produces the same file the office needs.
 */
import { formatDate, formatNumber, showToast } from '../ui.js';

const INSTITUTION = {
    name: 'MINISTERIO DE MINERÍA Y METALURGIA',
    subtitle: '(MATERIALES Y SUMINISTROS)',
    address: 'Av. Mariscal Santa Cruz - Edificio Centro de Comunicaciones, Piso 14',
    city: 'La Paz, Bolivia',
};

const SIGNATURES = {
    request: ['SOLICITANTE', 'ENCARGADO DE ALMACENES Y SERVICIOS GENERALES', 'UNIDAD SOLICITANTE'],
    delivery: ['SOLICITANTE', 'ENCARGADO DE ALMACENES Y SERVICIOS GENERALES',
               'S.G. JEFE ADMINISTRATIVO Y RECURSOS HUMANOS'],
};

export function printRequestForm(request) {
    /**
     * Prints the SOLICITUD form: the request as the user filed it.
     */
    _print('FORMULARIO - SOLICITUD DE ALMACENES', _document(request, { delivery: false }));
}

export function printDeliveryForm(request) {
    /**
     * Prints the ENTREGA form: adds who handed the material over, when, and
     * the quantity actually delivered per line.
     */
    _print('FORMULARIO - ENTREGA DE ALMACENES', _document(request, { delivery: true }));
}

function _document(request, { delivery }) {
    const title = delivery
        ? 'FORMULARIO - ENTREGA DE ALMACENES'
        : 'FORMULARIO - SOLICITUD DE ALMACENES';

    const rows = request.details.map(line => {
        const cells = [
            _cell(line.item_code || `#${line.item_id}`),
            _cell(line.unit || '—'),
            _cell(line.item_name || '—', 'left'),
            _cell(formatNumber(line.requested_qty)),
        ];
        if (delivery) cells.push(_cell(formatNumber(line.delivered_qty)));
        return `<tr>${cells.join('')}</tr>`;
    }).join('');

    const headers = ['CÓDIGO', 'UNIDAD', 'DESCRIPCIÓN',
                     delivery ? 'CANTIDAD SOLICITADA' : 'CANTIDAD'];
    if (delivery) headers.push('CANTIDAD ENTREGADA');

    const meta = [
        ['Nro de solicitud', request.code],
        delivery ? ['Entregado por', request.delivered_by || '—'] : null,
        ['Solicitado por', request.requester_name || request.requester_email],
        ['Cargo del solicitante', request.requester_position || '—'],
        ['Dirección / Unidad', request.requester_unit || '—'],
        ['Fecha de solicitud', formatDate(request.requested_at)],
        delivery ? ['Fecha de entrega', formatDate(request.delivered_at)] : null,
    ].filter(Boolean);

    return `
        <header class="doc-head">
            <h1>${_escape(INSTITUTION.name)}</h1>
            <p class="doc-sub">${_escape(INSTITUTION.subtitle)}</p>
            <h2>${_escape(title)}</h2>
        </header>
        <table class="doc-meta">
            ${meta.map(([label, value]) => `
                <tr><th>${_escape(label)}:</th><td>${_escape(String(value))}</td></tr>
            `).join('')}
        </table>
        <table class="doc-lines">
            <thead><tr>${headers.map(h => `<th>${_escape(h)}</th>`).join('')}</tr></thead>
            <tbody>${rows}</tbody>
        </table>
        <p class="doc-justification">
            <strong>Justificación:</strong>
            ${_escape(request.notes || 'El usuario no registró justificación.')}
        </p>
        <div class="doc-signatures">
            ${(delivery ? SIGNATURES.delivery : SIGNATURES.request)
                .map(label => `<div class="doc-sign"><span></span><p>${_escape(label)}</p></div>`)
                .join('')}
        </div>
        <footer class="doc-foot">
            <p>${_escape(INSTITUTION.name)}</p>
            <p>${_escape(INSTITUTION.address)}</p>
            <p>${_escape(INSTITUTION.city)}</p>
        </footer>
    `;
}

function _cell(value, align = 'center') {
    return `<td class="align-${align}">${_escape(String(value))}</td>`;
}

function _escape(text) {
    return String(text ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

function _print(title, bodyHtml) {
    const win = window.open('', '_blank', 'width=1024,height=760');
    if (!win) {
        showToast('Permite las ventanas emergentes para imprimir el formulario.', 'warning');
        return;
    }
    win.document.write(`
        <!DOCTYPE html><html lang="es"><head><meta charset="utf-8">
        <title>${_escape(title)}</title>
        <style>${_STYLES}</style>
        </head><body>${bodyHtml}</body></html>
    `);
    win.document.close();
    win.focus();
    // The document has to be laid out before the dialog opens, otherwise the
    // preview can come out blank in Chrome.
    win.setTimeout(() => win.print(), 250);
}

const _STYLES = `
    @page { size: letter; margin: 14mm; }
    body {
        font-family: Arial, Helvetica, sans-serif;
        font-size: 11px;
        color: #000;
        margin: 0;
    }
    .doc-head { text-align: center; margin-bottom: 14px; }
    .doc-head h1 { font-size: 13px; margin: 0; letter-spacing: 1px; }
    .doc-head h2 { font-size: 12px; margin: 10px 0 0; text-decoration: underline; }
    .doc-sub { margin: 2px 0 0; font-size: 10px; }
    .doc-meta { border-collapse: collapse; margin-bottom: 12px; }
    .doc-meta th {
        text-align: left;
        font-weight: bold;
        padding: 1px 10px 1px 0;
        white-space: nowrap;
    }
    .doc-meta td { padding: 1px 0; }
    .doc-lines { width: 100%; border-collapse: collapse; margin-bottom: 12px; }
    .doc-lines th, .doc-lines td { border: 1px solid #000; padding: 4px 6px; }
    .doc-lines th { font-size: 10px; background: #eee; }
    .align-center { text-align: center; }
    .align-left { text-align: left; }
    .doc-justification { margin: 0 0 34px; }
    /* Three signature blocks across the page, as on the paper form. */
    .doc-signatures {
        display: flex;
        justify-content: space-between;
        gap: 16px;
        margin-bottom: 26px;
    }
    .doc-sign { flex: 1; text-align: center; }
    .doc-sign span {
        display: block;
        border-top: 1px solid #000;
        margin: 40px 6px 4px;
    }
    .doc-sign p { margin: 0; font-size: 9px; font-weight: bold; }
    .doc-foot { text-align: center; font-size: 9px; border-top: 1px solid #000; padding-top: 6px; }
    .doc-foot p { margin: 1px 0; }
`;
