'''
    Siembra una farmacia de demostración en BILLING.

    Escribe con la API del servicio, no directo en DynamoDB: así los lotes, la
    numeración y el descuento de stock salen del mismo código que atiende al
    mostrador, y lo sembrado es exactamente lo que produciría un día de trabajo
    real. Sembrar por debajo dejaría datos que el servicio nunca habría creado.

    El catálogo son medicamentos comunes de una farmacia boliviana, con lotes
    escalonados a propósito: uno ya vencido, dos por vencer dentro de la
    alerta, y el resto lejos. Eso es lo que hace visible el FEFO y el tablero.

    Uso:
        python tools/billing/seed_demo.py --token <jwt>
        python tools/billing/seed_demo.py --token <jwt> --base http://localhost:3004
        python tools/billing/seed_demo.py --token <jwt> --wipe   # sólo agrega, ver abajo
'''
import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

DEFAULT_BASE = 'http://localhost:3004'
ROOT = '/v1/billing'

TODAY = date.today()

# (sku, descripción, laboratorio, código de barras, mínimo)
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

# (sku, cantidad, costo, precio, lote, días hasta el vencimiento)
# Los negativos son lotes ya vencidos: el tablero tiene que separarlos.
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

# (sku, unidades, descuento) — ventas de ejemplo para que el tablero no abra vacío.
SALES = (
    ((('PARA500', 2, 0), ('VITC-1G', 1, 0)), 'EFECTIVO', 'Juan Pérez', '9876543'),
    ((('IBU400', 1, 0),), 'QR', None, None),
    ((('AMOX500', 1, 5.0), ('SUERO-1L', 1, 0)), 'TARJETA', 'Clínica del Sur', '1029384756'),
    ((('BARBIJO-N95', 10, 0),), 'EFECTIVO', None, None),
    ((('LORA10', 2, 0), ('OMEP20', 1, 0)), 'QR', 'María Quispe', '6543210'),
)


class Api:
    '''
        Cliente mínimo del servicio, con el token del usuario que siembra.
    '''

    def __init__(
        self,
        base: str,
        token: str
    ):
        self.base = base.rstrip('/')
        self.token = token

    def call(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None
    ) -> Any:
        '''
            Una llamada al servicio.

            Args:
                method (str): Verbo HTTP.
                path (str): Ruta bajo /v1/billing.
                body (dict | None): Cuerpo JSON, si lo lleva.

            Returns:
                Any: La respuesta decodificada.

            Raises:
                RuntimeError: El servicio respondió con un error.
        '''
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            f'{self.base}{ROOT}{path}', data = data, method = method,
            headers = {
                'Authorization': f'Bearer {self.token}',
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
        Deja la farmacia lista para usar.

        Args:
            api (Api): Cliente del servicio.
            skip_existing (bool): Seguir aunque el SKU ya esté registrado.
    '''
    print('Configuración del comercio…')
    api.call('PUT', '/settings', SETTINGS)

    print(f'Catálogo: {len(CATALOGUE)} productos')
    for sku, description, laboratory, barcode, minimum in CATALOGUE:
        try:
            api.call('POST', '/products', {
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
        note = api.call('POST', '/purchases', {
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
        note = api.call('POST', '/sales', {
            'payment_method': method,
            'buyer': {'name': buyer, 'document': document},
            'lines': [{'sku': sku, 'quantity': units, 'discount': discount}
                      for sku, units, discount in lines]
        })
        print(f'  {note["number"]}  Bs {note["total"]:,.2f}  margen Bs {note["margin"]:,.2f}')


def main() -> int:
    '''
        Punto de entrada.

        Returns:
            int: 0 si sembró, 1 si el servicio rechazó algo.
    '''
    parser = argparse.ArgumentParser(description = 'Siembra una farmacia de demostración.')
    parser.add_argument('--token', required = True, help = 'JWT de un ADMIN o MANAGER.')
    parser.add_argument('--base', default = DEFAULT_BASE)
    parser.add_argument('--skip-existing', action = 'store_true',
                        help = 'No falla si el catálogo ya estaba sembrado.')
    args = parser.parse_args()

    try:
        seed(Api(args.base, args.token), args.skip_existing)
    except RuntimeError as error:
        print(f'\n{error}', file = sys.stderr)
        return 1

    print('\nListo.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
