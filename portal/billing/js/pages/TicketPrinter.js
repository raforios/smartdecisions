/**
 * TicketPrinter — the nota de venta on thermal paper.
 *
 * Printed from the browser, like the badges of MINING_SUMMIT: no driver, no
 * native app, no escape codes. A thermal printer installed in Windows is a
 * normal printer, so a page sized to the roll and a `@media print` block are
 * all it takes — and the same markup previews on screen before anyone burns
 * paper.
 *
 * The roll is 58 or 80 mm wide and endless: the height is whatever the note
 * needs, which is why the page size is declared in millimetres with `auto`
 * height. Fixing it to A4 is what makes a till spit out three blank pages.
 */
import { BillingService, errorText } from '../services/BillingService.js';
import { notify } from '../ui.js';

const WIDTHS = {
    MM_58: { page: '58mm', body: '54mm', font: '10px', columns: [26, 5, 10] },
    MM_80: { page: '80mm', body: '72mm', font: '11px', columns: [34, 6, 14] }
};

const money = (value) => Number(value || 0).toLocaleString('es-BO', {
    minimumFractionDigits: 2, maximumFractionDigits: 2
});

const escape = (value) => String(value ?? '').replace(/[&<>"]/g,
    (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[char]));

/** A date as a till prints it: day, month, year and the time of the sale. */
function stamp(iso) {
    if (!iso) return '';
    const [date, rest = ''] = iso.split('T');
    const [year, month, day] = date.split('-');
    return `${day}/${month}/${year} ${rest.slice(0, 5)}`;
}

/**
 * One product line. A line that took units from two batches at different
 * prices prints one row per price: the customer has to be able to add up what
 * they are being charged.
 */
function lineRows(line) {
    const prices = new Set(line.allocations.map((one) => one.unit_price));
    if (prices.size <= 1) {
        const price = line.allocations[0]?.unit_price ?? 0;
        return [{ name: line.description, quantity: line.quantity,
                  price, amount: line.subtotal }];
    }
    return line.allocations.map((allocation) => ({
        name: line.description,
        quantity: allocation.quantity,
        price: allocation.unit_price,
        amount: allocation.amount
    }));
}

/** The roll's stylesheet, shared by the internal note and the invoice. */
function styles(size) {
    return `
    @page { size: ${size.page} auto; margin: 2mm; }
    * { box-sizing: border-box; }
    body {
        width: ${size.body};
        margin: 0 auto;
        font-family: 'Courier New', Courier, monospace;
        font-size: ${size.font};
        line-height: 1.35;
        color: #000;
    }
    .center { text-align: center; }
    .name { font-weight: 700; font-size: calc(${size.font} + 3px); }
    .rule { border-top: 1px dashed #000; margin: 4px 0; }
    table { width: 100%; border-collapse: collapse; }
    td { vertical-align: top; padding: 0; }
    .item { font-weight: 700; }
    .qty { white-space: nowrap; }
    .amount { text-align: right; white-space: nowrap; }
    .totals td { padding-top: 1px; }
    .grand { font-weight: 700; font-size: calc(${size.font} + 2px); }
    .void {
        text-align: center; font-weight: 700; letter-spacing: 2px;
        border: 2px solid #000; padding: 3px; margin: 4px 0;
    }
    .foot { margin-top: 6px; text-align: center; }
    @media screen {
        body { padding: 8px; background: #fff;
               box-shadow: 0 0 0 1px #dbe4f0; margin: 12px auto; }
    }
    .qr { display: block; width: 32mm; height: 32mm; margin: 4px auto; }
    .qr svg { width: 100%; height: 100%; }
    .code { word-break: break-all; }
    .small { font-size: calc(${size.font} - 1px); }
`;
}

/**
 * The note as printable HTML.
 *
 * @param {object} sale Nota de venta as the service returned it.
 * @param {object} settings Trade name, NIT, address and footer of the shop.
 * @param {string} width MM_58 or MM_80.
 * @param {string} qrSvg The invoice's QR, from `invoiceQr`; empty on a note.
 * @returns {string} A complete document, ready for an iframe or a window.
 */
export function ticketHtml(sale, settings, width = 'MM_80', qrSvg = '') {
    const size = WIDTHS[width] || WIDTHS.MM_80;
    if (sale.invoice) return invoiceHtml(sale, { settings, size, qrSvg });
    const rows = sale.lines.flatMap(lineRows);

    const header = [
        `<div class="name">${escape(settings.trade_name)}</div>`,
        settings.document ? `<div>NIT ${escape(settings.document)}</div>` : '',
        settings.address ? `<div>${escape(settings.address)}</div>` : '',
        settings.phone ? `<div>Tel. ${escape(settings.phone)}</div>` : ''
    ].filter(Boolean).join('');

    const buyer = [
        sale.buyer?.name ? `<div>Cliente: ${escape(sale.buyer.name)}</div>` : '',
        sale.buyer?.document ? `<div>NIT/CI: ${escape(sale.buyer.document)}</div>` : ''
    ].filter(Boolean).join('');

    const body = rows.map((row) => `
        <tr>
            <td colspan="3" class="item">${escape(row.name)}</td>
        </tr>
        <tr>
            <td class="qty">${money(row.quantity)} x ${money(row.price)}</td>
            <td></td>
            <td class="amount">${money(row.amount)}</td>
        </tr>`).join('');

    const discount = sale.discount > 0
        ? `<tr><td colspan="2">Descuentos</td><td class="amount">-${money(sale.discount)}</td></tr>`
        : '';

    return `<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<title>Nota ${escape(sale.number)}</title>
<style>${styles(size)}</style></head>
<body>
    <div class="center">${header}</div>
    <div class="rule"></div>
    <div><strong>NOTA DE VENTA ${escape(sale.number)}</strong></div>
    <div>${stamp(sale.created_at)}</div>
    <div>Atendió: ${escape(sale.created_by)}</div>
    ${buyer}
    ${sale.status === 'CANCELLED' ? '<div class="void">ANULADA</div>' : ''}
    <div class="rule"></div>
    <table>${body}</table>
    <div class="rule"></div>
    <table class="totals">
        <tr><td colspan="2">Subtotal</td><td class="amount">${money(sale.subtotal)}</td></tr>
        ${discount}
        <tr class="grand"><td colspan="2">TOTAL Bs</td>
            <td class="amount">${money(sale.total)}</td></tr>
    </table>
    <div class="rule"></div>
    <div>Forma de pago: ${escape(sale.payment_method)}</div>
    ${sale.notes ? `<div>${escape(sale.notes)}</div>` : ''}
    <div class="foot">
        ${settings.ticket_footer ? escape(settings.ticket_footer) : '¡Gracias por su compra!'}
        <div class="rule"></div>
        <div>Documento interno. No es factura fiscal.</div>
    </div>
</body></html>`;
}

const UNITS = ['', 'uno', 'dos', 'tres', 'cuatro', 'cinco', 'seis', 'siete', 'ocho', 'nueve',
    'diez', 'once', 'doce', 'trece', 'catorce', 'quince', 'dieciséis', 'diecisiete',
    'dieciocho', 'diecinueve', 'veinte', 'veintiuno', 'veintidós', 'veintitrés',
    'veinticuatro', 'veinticinco', 'veintiséis', 'veintisiete', 'veintiocho', 'veintinueve'];
const TENS = ['', '', '', 'treinta', 'cuarenta', 'cincuenta', 'sesenta', 'setenta',
    'ochenta', 'noventa'];
const HUNDREDS = ['', 'ciento', 'doscientos', 'trescientos', 'cuatrocientos', 'quinientos',
    'seiscientos', 'setecientos', 'ochocientos', 'novecientos'];

/** Below a thousand, in words. */
function belowThousand(number) {
    if (number === 100) return 'cien';
    const hundreds = HUNDREDS[Math.floor(number / 100)];
    const rest = number % 100;
    const tail = rest < 30 ? UNITS[rest]
        : `${TENS[Math.floor(rest / 10)]}${rest % 10 ? ` y ${UNITS[rest % 10]}` : ''}`;
    return [hundreds, tail].filter(Boolean).join(' ');
}

/** A whole number in words, up to the hundreds of millions. */
function inWords(number) {
    if (number === 0) return 'cero';
    const millions = Math.floor(number / 1e6);
    const thousands = Math.floor((number % 1e6) / 1000);
    const rest = number % 1000;
    return [
        millions === 1 ? 'un millón' : millions ? `${inWords(millions)} millones` : '',
        thousands === 1 ? 'mil' : thousands ? `${belowThousand(thousands)} mil` : '',
        belowThousand(rest)
    ].filter(Boolean).join(' ')
        .replace(/veintiuno( mil| millones)/g, 'veintiún$1')
        .replace(/uno( mil| millones)/g, 'un$1');
}

/** The total as the invoice writes it out: "Son: Trescientos 00/100 Bolivianos". */
export function amountInWords(amount) {
    const cents = Math.round(Number(amount || 0) * 100);
    const words = inWords(Math.floor(cents / 100));
    return `Son: ${words.charAt(0).toUpperCase()}${words.slice(1)} ${
        String(cents % 100).padStart(2, '0')}/100 Bolivianos`;
}

/**
 * The invoice details of a line: one per price, the discount spent from the
 * first, exactly as the service built the XML.
 */
function invoiceRows(line) {
    const byPrice = new Map();
    for (const allocation of line.allocations) {
        byPrice.set(allocation.unit_price,
                    (byPrice.get(allocation.unit_price) || 0) + allocation.quantity);
    }
    let remaining = line.discount || 0;
    return [...byPrice].map(([price, quantity]) => {
        const amount = Math.round(price * quantity * 100) / 100;
        const discount = Math.min(remaining, amount);
        remaining -= discount;
        return { sku: line.sku, name: line.description, quantity, price, discount,
                 amount: Math.round((amount - discount) * 100) / 100 };
    });
}

/**
 * The invoice's graphic representation on the roll: what the SIN asks to be
 * printed of a computerised online invoice, with the CUF and the link its QR
 * carries.
 *
 * @param {object} sale Sale with its `invoice`.
 * @param {object} paper The shop's `settings`, the roll's `size` (one of
 *     WIDTHS) and the `qrSvg` the service drew.
 * @returns {string} A complete document.
 */
function invoiceHtml(sale, { settings, size, qrSvg }) {
    const invoice = sale.invoice;
    const place = invoice.branch ? `Sucursal N° ${invoice.branch}` : 'Casa Matriz';
    const body = sale.lines.flatMap(invoiceRows).map((row) => `
        <tr><td colspan="3" class="item">${escape(row.sku)} - ${escape(row.name)}</td></tr>
        <tr>
            <td class="qty">${money(row.quantity)} x ${money(row.price)}${
                row.discount ? ` - ${money(row.discount)}` : ''}</td>
            <td></td>
            <td class="amount">${money(row.amount)}</td>
        </tr>`).join('');

    return `<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<title>Factura ${invoice.number}</title>
<style>${styles(size)}</style></head>
<body>
    <div class="center">
        <div class="name">FACTURA</div>
        <div>(Con Derecho a Crédito Fiscal)</div>
        <div class="name">${escape(settings.trade_name)}</div>
        <div>${place}</div>
        <div>No. Punto de Venta ${invoice.point_of_sale}</div>
        <div>${escape(invoice.address)}</div>
        ${settings.phone ? `<div>Teléfono: ${escape(settings.phone)}</div>` : ''}
        ${settings.municipality ? `<div>${escape(settings.municipality)}</div>` : ''}
    </div>
    <div class="rule"></div>
    <div class="center">
        <div><strong>NIT</strong> ${escape(settings.document)}</div>
        <div><strong>FACTURA N°</strong> ${invoice.number}</div>
        <div><strong>CÓD. AUTORIZACIÓN</strong></div>
        <div class="code">${escape(invoice.cuf)}</div>
    </div>
    <div class="rule"></div>
    <div>NOMBRE/RAZÓN SOCIAL: ${escape(sale.buyer?.name || 'S/N')}</div>
    <div>NIT/CI/CEX: ${escape(sale.buyer?.document)}</div>
    <div>COD. CLIENTE: ${escape(sale.buyer?.document)}</div>
    <div>FECHA DE EMISIÓN: ${stamp(invoice.issued_at)}</div>
    ${sale.status === 'CANCELLED' ? '<div class="void">ANULADA</div>' : ''}
    <div class="rule"></div>
    <div class="center"><strong>DETALLE</strong></div>
    <table>${body}</table>
    <div class="rule"></div>
    <table class="totals">
        <tr><td colspan="2">SUBTOTAL Bs</td><td class="amount">${money(sale.total)}</td></tr>
        <tr><td colspan="2">DESCUENTO Bs</td><td class="amount">0,00</td></tr>
        <tr><td colspan="2">TOTAL Bs</td><td class="amount">${money(sale.total)}</td></tr>
        <tr><td colspan="2">MONTO GIFT CARD Bs</td><td class="amount">0,00</td></tr>
        <tr class="grand"><td colspan="2">MONTO A PAGAR Bs</td>
            <td class="amount">${money(sale.total)}</td></tr>
        <tr><td colspan="2">IMPORTE BASE CRÉDITO FISCAL Bs</td>
            <td class="amount">${money(sale.total)}</td></tr>
    </table>
    <div>${amountInWords(sale.total)}</div>
    <div class="rule"></div>
    <div class="foot small">
        <div>ESTA FACTURA CONTRIBUYE AL DESARROLLO DEL PAÍS, EL USO ILÍCITO SERÁ
             SANCIONADO PENALMENTE DE ACUERDO A LEY</div>
        <div class="rule"></div>
        <div>${escape(invoice.legend)}</div>
        <div class="rule"></div>
        <div>“Este documento es la Representación Gráfica de un Documento Fiscal
             Digital emitido en una modalidad de facturación en línea”</div>
        <!-- Drawn by the service from the link the invoice stored; it is
             our own SVG, so it goes in as markup. -->
        <div class="qr">${qrSvg}</div>
    </div>
</body></html>`;
}

/**
 * The QR of an invoice, as the service draws it; empty for an internal note.
 * A QR that cannot be fetched is said aloud: an invoice printed without it
 * is not a valid representation.
 *
 * @param {object} sale Sale, invoiced or not.
 * @returns {Promise<string>} Inline SVG, or ''.
 */
export async function invoiceQr(sale) {
    if (!sale.invoice) return '';
    try {
        return (await BillingService.saleQr(sale.sale_id)).svg;
    } catch (error) {
        notify(errorText(error, 'No se pudo dibujar el QR de la factura.'), 'error');
        return '';
    }
}

/**
 * Sends the note to the printer without leaving the page.
 *
 * A hidden iframe instead of `window.open`: a pop-up blocker eats the second
 * sale of the day, and the cashier never finds out why nothing printed.
 *
 * @param {object} sale Nota de venta.
 * @param {object} settings Shop parameters.
 * @param {string} width MM_58 or MM_80.
 */
export async function printTicket(sale, settings, width) {
    const qrSvg = await invoiceQr(sale);
    const frame = document.createElement('iframe');
    frame.setAttribute('aria-hidden', 'true');
    frame.style.cssText = 'position:fixed;right:0;bottom:0;width:0;height:0;border:0;';
    document.body.appendChild(frame);

    frame.contentDocument.open();
    frame.contentDocument.write(ticketHtml(sale, settings, width, qrSvg));
    frame.contentDocument.close();

    // The roll has no page count to wait for, but the fonts do: printing
    // before they load prints the fallback and the columns drift.
    const fire = () => {
        frame.contentWindow.focus();
        frame.contentWindow.print();
        setTimeout(() => frame.remove(), 1000);
    };
    if (frame.contentDocument.readyState === 'complete') fire();
    else frame.contentWindow.addEventListener('load', fire);
}
