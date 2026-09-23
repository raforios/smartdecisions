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

/**
 * The note as printable HTML.
 *
 * @param {object} sale Nota de venta as the service returned it.
 * @param {object} settings Trade name, NIT, address and footer of the shop.
 * @param {string} width MM_58 or MM_80.
 * @returns {string} A complete document, ready for an iframe or a window.
 */
export function ticketHtml(sale, settings, width = 'MM_80') {
    const size = WIDTHS[width] || WIDTHS.MM_80;
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
<style>
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
</style></head>
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
export function printTicket(sale, settings, width) {
    const frame = document.createElement('iframe');
    frame.setAttribute('aria-hidden', 'true');
    frame.style.cssText = 'position:fixed;right:0;bottom:0;width:0;height:0;border:0;';
    document.body.appendChild(frame);

    frame.contentDocument.open();
    frame.contentDocument.write(ticketHtml(sale, settings, width));
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
