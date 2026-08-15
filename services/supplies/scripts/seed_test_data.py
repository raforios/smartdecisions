'''
    Seed Supplies-Service with demo data.

    Drives the Supplies API via HTTP so it works regardless of where the
    database lives (local Docker, RDS, etc.). The caller logs in once and
    the same JWT is reused for catalog + stock + (optionally) sample
    requests in different lifecycle states.

    Usage examples:
        # Catalog + stock only (safe to demo to anyone)
        python seed_test_data.py \
            --admin-email raforios@gmail.com \
            --admin-password '***'

        # Catalog + stock + sample requests in various states
        python seed_test_data.py \
            --admin-email raforios@gmail.com \
            --admin-password '***' \
            --include-requests

        # Custom endpoints
        python seed_test_data.py --admin-email ... --admin-password ... \
            --auth-url https://32652ile50.execute-api.us-east-1.amazonaws.com/v1/auth \
            --base-url http://localhost:3004/v1/supplies

    Idempotency:
        Catalog rows (categories, units, items) are created with `code` as
        the natural key. The script tolerates 409 Conflict responses so a
        re-run does not break, but stock adjustments will compound on every
        run — only call it once per fresh database (or pass --skip-stock).
'''
import argparse
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests


# --------------------------------------------------------------------- #
# Catalog definitions                                                   #
# --------------------------------------------------------------------- #
CATEGORIES = [
    {'code': 'ESCR', 'name': 'Material de escritorio',
     'description': 'Lápices, borradores, reglas, etc.'},
    {'code': 'LIMP', 'name': 'Material de limpieza',
     'description': 'Detergentes, escobas, trapeadores y similares.'},
    {'code': 'COMP', 'name': 'Insumos de computo',
     'description': 'Periféricos y cables consumibles.'},
    {'code': 'PAPL', 'name': 'Papeleria general',
     'description': 'Hojas, sobres, folders.'},
    {'code': 'SEGU', 'name': 'Equipos de seguridad',
     'description': 'EPP basico para personal.'},
]

UNITS = [
    {'code': 'UND',  'name': 'Unidad',     'abbreviation': 'und'},
    {'code': 'CAJA', 'name': 'Caja',       'abbreviation': 'caja'},
    {'code': 'PAQ',  'name': 'Paquete',    'abbreviation': 'paq'},
    {'code': 'KG',   'name': 'Kilogramo',  'abbreviation': 'kg'},
]


@dataclass
class SeedStock:
    '''
        Opening figures of a demo item: its minimum, its replenishment size,
        the quantity it starts with and the cost of that first PEPS layer.
    '''
    min_stock: float
    default_replenishment_qty: float
    initial_stock: float
    unit_cost: float = 2.0


@dataclass
class SeedItem:
    '''
        One catalog item of the demo dataset, with its opening stock figures.
    '''
    code: str
    name: str
    category_code: str
    unit_code: str
    stock: SeedStock
    description: Optional[str] = None


ITEMS: List[SeedItem] = [
    SeedItem('ESCR-001', 'Lapiceros azules x 12',
             'ESCR', 'UND', SeedStock(20, 100, 80),
             description='Caja de 12 lapiceros tinta azul punta media.'),
    SeedItem('ESCR-002', 'Borradores blancos',
             'ESCR', 'UND', SeedStock(10, 50, 35)),
    SeedItem('ESCR-003', 'Reglas 30cm acrilicas',
             'ESCR', 'UND', SeedStock(5, 25, 18)),
    SeedItem('ESCR-004', 'Tijeras de oficina',
             'ESCR', 'UND', SeedStock(5, 15, 12)),
    SeedItem('LIMP-001', 'Detergente liquido 1L',
             'LIMP', 'UND', SeedStock(5, 20, 16)),
    SeedItem('LIMP-002', 'Escobas industriales',
             'LIMP', 'UND', SeedStock(3, 10, 7)),
    SeedItem('LIMP-003', 'Trapeadores microfibra',
             'LIMP', 'UND', SeedStock(5, 15, 11)),
    SeedItem('LIMP-004', 'Papel higienico jumbo',
             'LIMP', 'PAQ', SeedStock(8, 40, 28)),
    SeedItem('COMP-001', 'Mouse USB optico',
             'COMP', 'UND', SeedStock(5, 20, 14)),
    SeedItem('COMP-002', 'Teclado USB en espanol',
             'COMP', 'UND', SeedStock(5, 15, 9)),
    SeedItem('COMP-003', 'Cables HDMI 1.5m',
             'COMP', 'UND', SeedStock(3, 12, 6)),
    SeedItem('PAPL-001', 'Papel bond A4 75g',
             'PAPL', 'PAQ', SeedStock(10, 50, 35),
             description='Resma de 500 hojas.'),
    SeedItem('PAPL-002', 'Sobres carta blancos',
             'PAPL', 'CAJA', SeedStock(5, 20, 13)),
    SeedItem('PAPL-003', 'Folders manila tamano carta',
             'PAPL', 'PAQ', SeedStock(10, 40, 25)),
    SeedItem('SEGU-001', 'Mascarillas N95',
             'SEGU', 'CAJA', SeedStock(5, 30, 18)),
]


# --------------------------------------------------------------------- #
# HTTP helpers                                                          #
# --------------------------------------------------------------------- #
class ApiError(Exception):
    '''
        Raised when the Supplies or AUTH API answers with an unexpected status.
    '''


def _request(method: str, url: str, token: Optional[str] = None,
             payload: Optional[Dict[str, Any]] = None) -> requests.Response:
    '''
        Issues an HTTP request against the API, attaching the bearer token and
        the JSON content type when they apply.
    '''
    headers: Dict[str, str] = {}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    if payload is not None:
        headers['Content-Type'] = 'application/json'
    return requests.request(method, url, headers=headers, json=payload, timeout=30)


def login(auth_url: str, email: str, password: str) -> str:
    '''
        Authenticates against AUTH and returns the bearer access token.
    '''
    response = _request('POST', f'{auth_url}/login',
                        payload={'email': email, 'password': password})
    if not response.ok:
        raise ApiError(f'Login failed: {response.status_code} {response.text}')
    return response.json()['access_token']


def _post(base_url: str, path: str, token: str,
          payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    response = _request('POST', f'{base_url}{path}', token=token, payload=payload)
    if response.status_code == 409:
        # Idempotent: code already exists. Caller decides what to do.
        return None
    if not response.ok:
        raise ApiError(f'POST {path} failed: {response.status_code} {response.text}')
    return response.json() if response.text else None


def _put(base_url: str, path: str, token: str,
         payload: Dict[str, Any]) -> Dict[str, Any]:
    response = _request('PUT', f'{base_url}{path}', token=token, payload=payload)
    if not response.ok:
        raise ApiError(f'PUT {path} failed: {response.status_code} {response.text}')
    return response.json()


def _patch(base_url: str, path: str, token: str,
           payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    response = _request('PATCH', f'{base_url}{path}', token=token,
                        payload=payload if payload is not None else {})
    if not response.ok:
        raise ApiError(f'PATCH {path} failed: {response.status_code} {response.text}')
    return response.json()


def _get_list(base_url: str, path: str, token: str) -> List[Dict[str, Any]]:
    response = _request('GET', f'{base_url}{path}', token=token)
    if not response.ok:
        raise ApiError(f'GET {path} failed: {response.status_code} {response.text}')
    return response.json()


# --------------------------------------------------------------------- #
# Seed steps                                                            #
# --------------------------------------------------------------------- #
def seed_categories(base_url: str, token: str) -> Dict[str, int]:
    '''
        Returns a map { category_code: category_id } so items can resolve
        their FK without an extra round-trip per item.
    '''
    print('-- Categorias')
    code_to_id: Dict[str, int] = {}
    for entry in CATEGORIES:
        created = _post(base_url, '/categories', token, entry)
        if created is None:
            print(f'   = {entry["code"]} ya existia, busco id')
        else:
            print(f'   + {entry["code"]} {entry["name"]}')

    for row in _get_list(base_url, '/categories?limit=500', token):
        code_to_id[row['code']] = row['id']
    return code_to_id


def seed_units(base_url: str, token: str) -> Dict[str, int]:
    '''
        Creates the demo units of measure and returns their code -> id map.
    '''
    print('-- Unidades')
    for entry in UNITS:
        created = _post(base_url, '/units', token, entry)
        if created is None:
            print(f'   = {entry["code"]} ya existia')
        else:
            print(f'   + {entry["code"]} {entry["name"]}')

    return {row['code']: row['id']
            for row in _get_list(base_url, '/units?limit=500', token)}


def seed_items(base_url: str, token: str,
               cat_ids: Dict[str, int], unit_ids: Dict[str, int]) -> Dict[str, int]:
    '''
        Creates the demo catalog items and returns their code -> id map.
    '''
    print('-- Items')
    for item in ITEMS:
        payload = {
            'code': item.code,
            'name': item.name,
            'description': item.description,
            'category_id': cat_ids[item.category_code],
            'unit_id': unit_ids[item.unit_code],
            'min_stock': item.stock.min_stock,
            'default_replenishment_qty': item.stock.default_replenishment_qty,
        }
        created = _post(base_url, '/items', token, payload)
        if created is None:
            print(f'   = {item.code} ya existia')
        else:
            print(f'   + {item.code} {item.name}')

    return {row['code']: row['id']
            for row in _get_list(base_url, '/items?limit=500', token)}


def seed_stock(base_url: str, token: str, item_ids: Dict[str, int]) -> None:
    '''
        Registers a single opening Nota de Ingreso whose detail lines create
        one PEPS/FIFO cost layer per item, bringing stock from 0 to
        item.stock.initial_stock. A cost layer (not a bare adjustment) is required
        so later deliveries have something to consume under FIFO.

        Not idempotent: re-running adds a second entry and compounds stock;
        only call it once per fresh database (or pass --skip-stock).
    '''
    print('-- Stock inicial via Nota de Ingreso')
    details = [
        {
            'item_id': item_ids[item.code],
            'quantity': item.stock.initial_stock,
            'unit_cost': item.stock.unit_cost,
        }
        for item in ITEMS if item.stock.initial_stock > 0
    ]
    payload = {
        'entry_type': 'COMPRA',
        'supplier': 'Proveedor demo inicial',
        'observations': 'Carga inicial de stock para pruebas (seed).',
        'details': details,
    }
    _post(base_url, '/entries', token, payload)
    print(f'   + Nota de Ingreso con {len(details)} items')


# --------------------------------------------------------------------- #
# Sample requests                                                       #
# --------------------------------------------------------------------- #
def seed_requests(base_url: str, token: str, item_ids: Dict[str, int]) -> None:
    '''
        Creates 5 sample requests as the logged-in user (typically ADMIN)
        and moves each one to a different state so the warehouse demo
        shows the full lifecycle on the dashboard.
    '''
    print('-- Solicitudes demo')

    sketches = [
        {
            'label': 'Solicitud 1 - permanece CREATED',
            'payload': {
                'notes': 'Pedido recien levantado por usuario.',
                'details': [
                    {'item_id': item_ids['ESCR-001'], 'requested_qty': 5},
                    {'item_id': item_ids['LIMP-001'], 'requested_qty': 2},
                ],
            },
            'transitions': [],
        },
        {
            'label': 'Solicitud 2 - tomada por almacen (IN_PROCESS)',
            'payload': {
                'notes': 'Operativo de oficina central.',
                'details': [
                    {'item_id': item_ids['COMP-001'], 'requested_qty': 1},
                ],
            },
            'transitions': ['process'],
        },
        {
            'label': 'Solicitud 3 - entregada, esperando conformidad',
            'payload': {
                'notes': 'Para la jefatura administrativa.',
                'details': [
                    {'item_id': item_ids['PAPL-001'], 'requested_qty': 3},
                    {'item_id': item_ids['PAPL-003'], 'requested_qty': 2},
                ],
            },
            'transitions': ['process', 'deliver'],
        },
        {
            'label': 'Solicitud 4 - ciclo completo cerrado',
            'payload': {
                'notes': 'Reposicion mensual de tinta y borradores.',
                'details': [
                    {'item_id': item_ids['ESCR-002'], 'requested_qty': 10},
                ],
            },
            'transitions': ['process', 'deliver', 'close'],
        },
        {
            'label': 'Solicitud 5 - rechazada (cantidad excesiva)',
            'payload': {
                'notes': 'Para evento masivo.',
                'details': [
                    {'item_id': item_ids['LIMP-004'], 'requested_qty': 1},
                ],
            },
            'transitions': [('process', None),
                            ('reject', 'No corresponde al area solicitante.')],
        },
    ]

    for sketch in sketches:
        print(f'   * {sketch["label"]}')
        created = _post(base_url, '/requests', token, sketch['payload'])
        if not created:
            print('     ! no se pudo crear (probablemente colision); continuo')
            continue
        request_id = created['id']

        # Small pause so created_at timestamps spread enough to read in the UI.
        time.sleep(0.4)

        for step in sketch['transitions']:
            if isinstance(step, tuple):
                action, reason = step
            else:
                action, reason = step, None
            _apply_transition(base_url, token, request_id, action, reason)


def _apply_transition(base_url: str, token: str, request_id: int,
                      action: str, reason: Optional[str]) -> None:
    paths = {
        'process': f'/requests/{request_id}/process',
        'deliver': f'/requests/{request_id}/deliver',
        'close':   f'/requests/{request_id}/close',
        'reject':  f'/requests/{request_id}/reject',
        'cancel':  f'/requests/{request_id}/cancel',
    }
    payload: Optional[Dict[str, Any]] = None
    if action in ('reject', 'cancel'):
        payload = {'reason': reason or 'Sin motivo registrado.'}
    elif action == 'deliver':
        payload = {}  # service defaults to requested quantities
    _patch(base_url, paths[action], token, payload)
    print(f'     -> {action.upper()} OK')


# --------------------------------------------------------------------- #
# Entry point                                                           #
# --------------------------------------------------------------------- #
def main() -> int:
    '''
        Parses the CLI arguments and runs the full seeding sequence.
    '''
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--admin-email', required=True)
    parser.add_argument('--admin-password', required=True)
    parser.add_argument('--auth-url', default='http://localhost:3000/v1/auth',
                        help='Base URL of the AUTH service (default local).')
    parser.add_argument('--base-url', default='http://localhost:3004/v1/supplies',
                        help='Base URL of the SUPPLIES service (default local).')
    parser.add_argument('--include-requests', action='store_true',
                        help='Seed 5 demo requests in various lifecycle states.')
    parser.add_argument('--skip-stock', action='store_true',
                        help='Skip stock adjustments (use when re-running).')
    args = parser.parse_args()

    try:
        print(f'Login en {args.auth_url} ...')
        token = login(args.auth_url, args.admin_email, args.admin_password)
        print('Login OK')

        cat_ids = seed_categories(args.base_url, token)
        unit_ids = seed_units(args.base_url, token)
        item_ids = seed_items(args.base_url, token, cat_ids, unit_ids)

        if not args.skip_stock:
            seed_stock(args.base_url, token, item_ids)
        else:
            print('-- Stock omitido (--skip-stock)')

        if args.include_requests:
            seed_requests(args.base_url, token, item_ids)

    except ApiError as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1
    except requests.RequestException as exc:
        print(f'ERROR de red: {exc}', file=sys.stderr)
        return 2

    print('\nSeed completado.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
