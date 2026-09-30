'''
    Runs one invoice through the whole chain, with the tax office simulated.

    It exists because the SIAT pilot answers 503 to everybody right now, and
    waiting for it would leave the entire pipeline untested. Everything here is
    ours and verifiable: the CUF, the XML, the validation against the SIN's own
    XSD, and the GZIP+base64 packing. The only thing simulated is the answer,
    which we could not know even with the service up.

    **It does not invent the WSDL, and that matters.** A made-up SOAP contract
    would make every test pass against our fiction and fail against the real
    service — the same mistake the XSD caught when the XML was written by hand,
    but with nothing to catch it. So the SOAP call is where this stops: what it
    proves is that the document we would send is a valid document.

    The CUFD and its control code are FAKE and marked as such in the output.
    They come from the tax office and nothing can derive them.

    Usage:
        python -m tools.billing.dry_run_invoice
        python -m tools.billing.dry_run_invoice --lines 3 --save /tmp/factura.xml
'''
import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

BILLING_PATH = Path(__file__).resolve().parents[2] / 'services' / 'billing'
XSD_PATH = Path(__file__).resolve().parents[2] / 'docs' / 'siat' / \
    'facturaComputarizadaCompraVenta.xsd'
sys.path.insert(0, str(BILLING_PATH))

# pylint: disable=wrong-import-position
from schemas.billing import (  # noqa: E402
    Buyer,
    CufInput,
    InvoiceContext,
    InvoiceLine,
    PaymentMethod,
    SaleLineOut,
    SaleNoteOut,
    SaleStatus
)
from services.billing_invoice_xml import (  # noqa: E402
    build_invoice_xml,
    validate_against_schema
)
from services.billing_siat import build_cuf, pack  # noqa: E402

# The pharmacy of the demo. Fictitious, and the NIT is deliberately not a real
# one: a document built with somebody's actual NIT is a document that could be
# mistaken for theirs.
PHARMACY = {
    'nit': '1234567890123',
    'trade_name': 'Farmacia Demo BearSoft',
    'municipality': 'La Paz',
    'address': 'Av. Arce 2020, Zona Sopocachi',
    'phone': '2211234',
    'branch': 0,
    'point_of_sale': 0
}

# What only the tax office can issue. FAKE: printed as such so nobody takes
# this output for a real fiscal document.
FAKE_CUFD = 'CUFD-SIMULADO-0001'
FAKE_CONTROL_CODE = 'A19E23EF34124CD'

# Bolivianos, and the rate of the currency against itself.
CURRENCY_BOB = 1
RATE_BOB = 1.0

# One of the legends the SIN's catalogue carries. It changes with each issue by
# law 453, so in production it is picked from the synchronised catalogue and
# never written here.
LEGEND = 'Ley N 453: El proveedor debe suministrar informacion clara y veraz.'

SAMPLE_PRODUCTS = [
    ('PARA500', 'Paracetamol 500 mg x 10 comprimidos', 2.0, 6.0, '477310', '99100', 57),
    ('IBUP400', 'Ibuprofeno 400 mg x 20 comprimidos', 1.0, 18.5, '477310', '99100', 57),
    ('AMOX500', 'Amoxicilina 500 mg x 12 capsulas', 3.0, 24.0, '477310', '99100', 57),
]


def _lines(count: int) -> List[InvoiceLine]:
    '''
        The invoice lines of the example.

        Args:
            count (int): How many products to bill.

        Returns:
            List[InvoiceLine]: The lines, homologated.
    '''
    return [
        InvoiceLine(
            sku = sku, description = description, quantity = quantity,
            unit_price = price, discount = 0.0,
            subtotal = round(quantity * price, 2),
            sin_activity_code = activity, sin_product_code = product,
            sin_unit_code = unit
        )
        for sku, description, quantity, price, activity, product, unit
        in SAMPLE_PRODUCTS[:count]
    ]


def _sale(lines: List[InvoiceLine]) -> SaleNoteOut:
    '''
        The sale as it would have been stored at the counter.

        Args:
            lines (List[InvoiceLine]): The lines being billed.

        Returns:
            SaleNoteOut: The issued note.
    '''
    total = round(sum(line.subtotal for line in lines), 2)
    return SaleNoteOut(
        sale_id = 'demo-0001',
        number = 'A-000001',
        status = SaleStatus.ISSUED,
        buyer = Buyer(name = 'Ana Quispe Mamani', document = '4567890',
                      document_type = 1),
        payment_method = PaymentMethod.EFECTIVO,
        created_by = 'cajera@farmacia.demo',
        created_at = datetime.now().isoformat(),
        lines = [
            SaleLineOut(
                sku = line.sku, description = line.description,
                quantity = line.quantity, discount = line.discount,
                allocations = [], subtotal = line.subtotal,
                total = line.subtotal, cost = round(line.subtotal * 0.6, 2)
            )
            for line in lines
        ],
        subtotal = total, discount = 0.0, total = total,
        cost = round(total * 0.6, 2), margin = round(total * 0.4, 2)
    )


def _report(
    step: int,
    title: str,
    detail: str
) -> None:
    '''
        Prints one step of the chain.

        Args:
            step (int): Step number.
            title (str): What it did.
            detail (str): What it produced.
    '''
    print(f'\n{step}. {title}')
    print(f'   {detail}')


def main(argument_list: Optional[list] = None) -> int:
    '''
        Entry point.

        Args:
            argument_list (list): Arguments, for tests. Defaults to argv.

        Returns:
            int: 0 when the document validates, 1 when it does not.
    '''
    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument('--lines', type = int, default = 2,
                        choices = range(1, len(SAMPLE_PRODUCTS) + 1),
                        help = 'How many products to bill.')
    parser.add_argument('--save', default = None, help = 'Write the XML here.')
    arguments = parser.parse_args(argument_list)

    print('=' * 72)
    print('SIMULACIÓN DE FACTURA — el SIAT está simulado, el resto es real')
    print('=' * 72)

    lines = _lines(arguments.lines)
    sale = _sale(lines)
    issued_at = datetime.now()
    _report(1, 'Venta emitida en el mostrador',
            f'{sale.number} · {len(lines)} línea(s) · Bs {sale.total}')

    cuf = build_cuf(CufInput(
        nit = PHARMACY['nit'], issued_at = issued_at, invoice_number = 1,
        branch = PHARMACY['branch'], point_of_sale = PHARMACY['point_of_sale']
    ), control_code = FAKE_CONTROL_CODE)
    _report(2, 'CUF generado por nuestro sistema',
            f'{cuf}\n   ({len(cuf)} caracteres · código de control SIMULADO)')

    context = InvoiceContext(
        issuer_document = PHARMACY['nit'], trade_name = PHARMACY['trade_name'],
        municipality = PHARMACY['municipality'], address = PHARMACY['address'],
        phone = PHARMACY['phone'], branch = PHARMACY['branch'],
        point_of_sale = PHARMACY['point_of_sale'], invoice_number = 1,
        cuf = cuf, cufd = FAKE_CUFD,
        issued_at = issued_at.replace(microsecond = 0).isoformat(),
        legend = LEGEND, currency_code = CURRENCY_BOB, exchange_rate = RATE_BOB
    )
    xml = build_invoice_xml(sale, context, lines)
    _report(3, 'XML armado contra el XSD del SIN', f'{len(xml)} bytes')

    problems = validate_against_schema(xml, str(XSD_PATH))
    if problems:
        _report(4, 'VALIDACIÓN CONTRA EL XSD: falló', '\n   '.join(problems))
        return 1
    _report(4, 'Validación contra el XSD del SIN', 'válido — 0 observaciones')

    packed = pack(xml)
    _report(5, 'Comprimido y codificado como viaja al SIAT',
            f'{len(xml)} bytes → {len(packed)} caracteres base64 '
            f'({100 - round(len(packed) / len(xml) * 100)}% menos)')

    _report(6, 'Envío al SIAT', 'NO se ejecuta. El ambiente piloto responde 503 '
                                'a todos,\n   y no se inventa el contrato SOAP: '
                                'un WSDL ficticio haría que\n   las pruebas pasen '
                                'contra nuestra invención y fallen contra el real.')

    if arguments.save:
        Path(arguments.save).write_text(xml, encoding = 'utf-8')
        print(f'\nXML guardado en {arguments.save}')

    print('\n' + '-' * 72)
    print('El documento que se enviaría es un documento VÁLIDO.')
    print('Falta sólo que el SIAT responda para probar el envío.')
    print('-' * 72)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
