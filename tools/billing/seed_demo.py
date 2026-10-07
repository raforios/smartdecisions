'''
    Seeds a demonstration pharmacy in BILLING.

    It writes through the service's API, not straight into DynamoDB: the lots,
    the numbering and the stock draw-down come out of the same code that serves
    the counter, so what is seeded is exactly what a real working day would
    produce. Seeding underneath would leave data the service never created.

    The catalogue is common medicines of a Bolivian pharmacy, with lots
    staggered on purpose: one already expired, two expiring inside the alert
    window, the rest far away. That is what makes FEFO and the dashboard show.

    Usage:
        python tools/billing/seed_demo.py --token <jwt>
        python tools/billing/seed_demo.py --token <jwt> --base http://localhost:3004
        python tools/billing/seed_demo.py --token <jwt> --skip-existing
'''
import argparse
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

DEFAULT_BASE = 'http://localhost:3004'
ROOT = '/v1/billing'

TODAY = date.today()

# (sku, description, laboratory, barcode, minimum stock)
CATALOGUE = (
    ('PARA500', 'Paracetamol 500 mg — caja x 10', 'Inti', '7770001000015', 20),
    ('IBU400', 'Ibuprofeno 400 mg — caja x 10', 'Inti', '7770001000022', 20),
    ('AMOX500', 'Amoxicilina 500 mg — caja x 12', 'Vita', '7770001000039', 12),
    ('OMEP20', 'Omeprazol 20 mg — caja x 14', 'Lafar', '7770001000046', 10),
    ('LORA10', 'Loratadina 10 mg — caja x 10', 'Vita', '7770001000053', 10),
    ('SALBU-INH', 'Salbutamol inhalador 100 mcg', 'Inti', '7770001000060', 5),
    ('SUERO-1L', 'Suero fisiológico 1 L', 'Lafar', '7770001000077', 8),
    ('VITC-1G', 'Vitamina C 1 g — tubo x 10', 'Bagó', '7770001000084', 15),
    ('ALCOHOL-250', 'Alcohol medicinal 250 ml', 'Droguería Inti', '7770001000091', 12),
    ('BARBIJO-N95', 'Barbijo N95 — unidad', 'Importado', '7770001000107', 30),
)

# (sku, quantity, cost, price, lot, days to expiry)
# Negative days are lots already expired: the dashboard has to set them apart.
DELIVERIES = (
    ('Droguería Inti S.A.', '84512', (
        ('PARA500', 60, 3.10, 6.50, 'L-2401', 400),
        ('PARA500', 24, 3.40, 7.00, 'L-2318', 45),
        ('IBU400', 40, 4.20, 9.00, 'L-2405', 300),
        ('SALBU-INH', 12, 38.00, 72.00, 'L-2377', 260),
        ('ALCOHOL-250', 30, 6.50, 12.00, 'L-2390', 500),
    )),
    ('Distribuidora Vita Ltda.', '84577', (
        ('AMOX500', 30, 12.00, 24.00, 'V-118', 210),
        ('LORA10', 25, 5.80, 12.50, 'V-120', 30),
        ('VITC-1G', 40, 7.20, 15.00, 'V-121', 365),
    )),
    ('Farma Bolivia SRL', '84603', (
        ('OMEP20', 20, 9.50, 19.00, 'F-77', 180),
        ('SUERO-1L', 15, 11.00, 20.00, 'F-78', -20),
        ('BARBIJO-N95', 50, 2.10, 5.00, 'F-79', 900),
    )),
)

SETTINGS = {
    'trade_name': 'Farmacia San Rafael',
    'document': '4829176018',
    'address': 'Av. Arce 2345, La Paz',
    'phone': '2 2441122',
    'sale_series': 'A',
    'purchase_series': 'C',
    'discounts_enabled': True,
    'ticket_width': 'MM_80',
    'ticket_footer': 'Consulte a su médico. Gracias por su preferencia.'
}

# (sku, units, discount) — sample sales, so the dashboard does not open empty.
SALES = (
    ((('PARA500', 2, 0), ('VITC-1G', 1, 0)), 'EFECTIVO', 'Juan Pérez', '9876543'),
    ((('IBU400', 1, 0),), 'QR', None, None),
    ((('AMOX500', 1, 5.0), ('SUERO-1L', 1, 0)), 'TARJETA', 'Clínica del Sur', '1029384756'),
    ((('BARBIJO-N95', 10, 0),), 'EFECTIVO', None, None),
    ((('LORA10', 2, 0), ('OMEP20', 1, 0)), 'QR', 'María Quispe', '6543210'),
)


@dataclass(frozen = True)
class Api:
    '''
        Where the service is, and the token of the user seeding it.
    '''
    base: str
    token: str


def call(
    api: Api,
    method: str,
    path: str,
    body: dict[str, Any] | None = None
) -> Any:
    '''
        One call to the service.

        Args:
            api (Api): Service and token.
            method (str): HTTP verb.
            path (str): Path under /v1/billing.
            body (dict | None): JSON body, if any.

        Returns:
            Any: The decoded answer.

        Raises:
            RuntimeError: The service answered with an error.
    '''
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        f'{api.base}{ROOT}{path}', data = data, method = method,
        headers = {
            'Authorization': f'Bearer {api.token}',
            'Accept': 'application/json',
            **({'Content-Type': 'application/json'} if data else {})
        }
    )
    try:
        with urllib.request.urlopen(request, timeout = 30) as response:
            payload = response.read()
        return json.loads(payload) if payload else None
    except urllib.error.HTTPError as error:
        detail = error.read().decode('utf-8', 'replace')
        raise RuntimeError(f'{method} {path} → {error.code} {detail}') from error


def seed(
    api: Api,
    skip_existing: bool
) -> None:
    '''
        Leaves the pharmacy ready to use.

        Args:
            api (Api): Service and token.
            skip_existing (bool): Carry on when a SKU is already registered.
    '''
    print('Configuración del comercio…')
    call(api, 'PUT', '/settings', SETTINGS)

    print(f'Catálogo: {len(CATALOGUE)} productos')
    for sku, description, laboratory, barcode, minimum in CATALOGUE:
        try:
            call(api, 'POST', '/products', {
                'sku': sku, 'description': description, 'laboratory': laboratory,
                'barcode': barcode, 'min_stock': minimum
            })
            print(f'  + {sku}')
        except RuntimeError as error:
            if skip_existing and 'SKU_ALREADY_EXISTS' in str(error):
                print(f'  = {sku} (ya estaba)')
                continue
            raise

    print(f'Recepciones: {len(DELIVERIES)}')
    for supplier, invoice, lines in DELIVERIES:
        note = call(api, 'POST', '/purchases', {
            'supplier_name': supplier,
            'invoice_number': invoice,
            'invoice_date': (TODAY - timedelta(days = 3)).isoformat(),
            'lines': [
                {
                    'sku': sku, 'quantity': quantity, 'unit_cost': cost,
                    'sale_price': price, 'lot_code': lot,
                    'expiry_date': (TODAY + timedelta(days = days)).isoformat()
                }
                for sku, quantity, cost, price, lot, days in lines
            ]
        })
        print(f'  {note["number"]}  {supplier}  Bs {note["total_cost"]:,.2f}')

    print(f'Ventas de ejemplo: {len(SALES)}')
    for lines, method, buyer, document in SALES:
        note = call(api, 'POST', '/sales', {
            'payment_method': method,
            'buyer': {'name': buyer, 'document': document},
            'lines': [{'sku': sku, 'quantity': units, 'discount': discount}
                      for sku, units, discount in lines]
        })
        print(f'  {note["number"]}  Bs {note["total"]:,.2f}  margen Bs {note["margin"]:,.2f}')


def main() -> int:
    '''
        Entry point.

        Returns:
            int: 0 when seeded, 1 when the service refused something.
    '''
    parser = argparse.ArgumentParser(description = 'Siembra una farmacia de demostración.')
    parser.add_argument('--token', required = True, help = 'JWT de un ADMIN o MANAGER.')
    parser.add_argument('--base', default = DEFAULT_BASE)
    parser.add_argument('--skip-existing', action = 'store_true',
                        help = 'No falla si el catálogo ya estaba sembrado.')
    args = parser.parse_args()

    try:
        seed(Api(args.base.rstrip('/'), args.token), args.skip_existing)
    except RuntimeError as error:
        print(f'\n{error}', file = sys.stderr)
        return 1

    print('\nListo.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
