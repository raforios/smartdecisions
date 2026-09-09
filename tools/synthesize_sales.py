'''
    Synthetic sales generator for the SmartDecisions POC.

    Produces a realistic Excel that matches `template_ventas_v1.xlsx` and
    contains *embedded affinities* so the analytics service shows non-trivial
    opportunities during demos:

        - 5 puntos de venta (PdVs) with distinct sales profiles.
        - 12 productos (SKUs) covering 4 categories.
        - Two strong affinities by design:
            * Galleta Integral ↔ Yogurt Natural (lift > 2)
            * Cerveza ↔ Snack Salado          (lift > 2)
        - Two PdVs deliberately *miss* one half of each affinity → the
          analytics engine should surface those as concrete opportunities.

    Run:
        python tools/synthesize_sales.py \\
            --output tools/samples/ventas_demo.xlsx \\
            --orders 1200 \\
            --seed 42

    The output is ready to upload through `/demo/excel/` or the
    `POST /v1/ingest/excel` endpoint.
'''
import argparse
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
import pandas as pd


# --- Catalog ---------------------------------------------------------------

PRODUCTS = [
    {'id_producto': 'SKU-A100', 'nombre_producto': 'Galleta Integral 200g',
     'precio_unitario': 8.5},
    {'id_producto': 'SKU-A101', 'nombre_producto': 'Galleta Chips 200g',
     'precio_unitario': 9.0},
    {'id_producto': 'SKU-B200', 'nombre_producto': 'Yogurt Natural 1L',
     'precio_unitario': 15.0},
    {'id_producto': 'SKU-B201', 'nombre_producto': 'Yogurt Frutilla 1L',
     'precio_unitario': 16.5},
    {'id_producto': 'SKU-C300', 'nombre_producto': 'Cerveza Pilsen 6-pack',
     'precio_unitario': 42.0},
    {'id_producto': 'SKU-C301', 'nombre_producto': 'Cerveza Negra 6-pack',
     'precio_unitario': 48.0},
    {'id_producto': 'SKU-D400', 'nombre_producto': 'Snack Salado 150g',
     'precio_unitario': 7.5},
    {'id_producto': 'SKU-D401', 'nombre_producto': 'Maní Salado 200g',
     'precio_unitario': 6.0},
    {'id_producto': 'SKU-E500', 'nombre_producto': 'Aceite Girasol 1L',
     'precio_unitario': 18.0},
    {'id_producto': 'SKU-E501', 'nombre_producto': 'Arroz 1kg',
     'precio_unitario': 12.5},
    {'id_producto': 'SKU-F600', 'nombre_producto': 'Detergente Líquido 1L',
     'precio_unitario': 22.0},
    {'id_producto': 'SKU-F601', 'nombre_producto': 'Jabón en Polvo 1kg',
     'precio_unitario': 17.0},
]

PDVS = [
    {'id_punto_venta': 'PDV-007', 'nombre_pdv': 'Tienda Doña Rosa',     'zona': 'Sur'},
    {'id_punto_venta': 'PDV-012', 'nombre_pdv': 'Mini-market El Sol',   'zona': 'Centro'},
    {'id_punto_venta': 'PDV-024', 'nombre_pdv': 'Despensa Las Flores',  'zona': 'Norte'},
    {'id_punto_venta': 'PDV-036', 'nombre_pdv': 'Bodega Lupita',        'zona': 'Sur'},
    {'id_punto_venta': 'PDV-048', 'nombre_pdv': 'Almacén San Pedro',    'zona': 'Centro'},
]


# --- Affinity matrix ------------------------------------------------------

@dataclass
class AffinityRule:
    '''
        Two products that should co-occur in the same order with the given
        probability whenever the first one is purchased.
    '''
    antecedent: str
    consequent: str
    cooccurrence_probability: float


AFFINITIES = [
    AffinityRule('SKU-A100', 'SKU-B200', 0.75),
    AffinityRule('SKU-A101', 'SKU-B201', 0.65),
    AffinityRule('SKU-C300', 'SKU-D400', 0.80),
    AffinityRule('SKU-C301', 'SKU-D401', 0.70),
    AffinityRule('SKU-E500', 'SKU-E501', 0.60),
]


# --- PdV profiles ---------------------------------------------------------

PDV_PROFILES = {
    # PdV-007 compra mucha galleta y yogurt → ya capta esa afinidad.
    'PDV-007': {'weights': {'SKU-A100': 5, 'SKU-A101': 3, 'SKU-B200': 5,
                            'SKU-B201': 2, 'SKU-D400': 1, 'SKU-E501': 2,
                            'SKU-F601': 1, 'SKU-D401': 1, 'SKU-E500': 1}},
    # PdV-012 compra mucha cerveza pero NO snacks → oportunidad clara.
    'PDV-012': {'weights': {'SKU-C300': 6, 'SKU-C301': 4, 'SKU-E501': 2,
                            'SKU-F600': 2, 'SKU-A100': 2}},
    # PdV-024 perfil amplio, base.
    'PDV-024': {'weights': {'SKU-A100': 2, 'SKU-A101': 2, 'SKU-B200': 2,
                            'SKU-C300': 2, 'SKU-D400': 1, 'SKU-D401': 1,
                            'SKU-E500': 2, 'SKU-E501': 3, 'SKU-F600': 1,
                            'SKU-F601': 1}},
    # PdV-036 compra solo galletas → oportunidad clara: yogurts.
    'PDV-036': {'weights': {'SKU-A100': 5, 'SKU-A101': 4, 'SKU-D400': 1,
                            'SKU-E501': 1}},
    # PdV-048 compra solo cerveza + maní → ya capta una afinidad,
    # oportunidad: snack salado.
    'PDV-048': {'weights': {'SKU-C301': 5, 'SKU-D401': 4, 'SKU-E500': 1,
                            'SKU-E501': 1}},
}

PRODUCT_BY_ID = {item['id_producto']: item for item in PRODUCTS}


# --- Generation -----------------------------------------------------------

def _weighted_choice(weights: dict, rng: random.Random) -> str:
    '''
        Picks one key from a {item: weight} mapping proportional to weights.
    '''
    items = list(weights.keys())
    weight_list = list(weights.values())
    return rng.choices(items, weights = weight_list, k = 1)[0]


def _basket_for_pdv(pdv_id: str, rng: random.Random) -> list:
    '''
        Generates one shopping basket (list of product ids) for the PdV.

        Affinity rules may inject products outside the PdV's regular catalog
        (that is exactly the signal we want analytics to pick up). To stay
        bounded we cap the target size at the count of SKUs reachable from the
        PdV (its own catalog plus the consequents of any rule whose antecedent
        the PdV stocks).
    '''
    profile = PDV_PROFILES[pdv_id]
    weights = dict(profile['weights'])

    # Compute how many distinct SKUs this PdV can ever end up with given its
    # own catalog + the consequents reachable through the affinity rules.
    reachable = set(weights.keys())
    for rule in AFFINITIES:
        if rule.antecedent in reachable:
            reachable.add(rule.consequent)
    max_basket = len(reachable)

    basket_size = min(rng.randint(2, 5), max_basket)
    basket = set()
    safety_iterations = 0
    max_safety = basket_size * 20

    while len(basket) < basket_size and safety_iterations < max_safety:
        safety_iterations += 1
        product_id = _weighted_choice(weights, rng)
        basket.add(product_id)
        # Apply affinity rules: if the antecedent is in the basket, the
        # consequent has a strong chance of being added too — even if the
        # PdV does not stock the consequent today (that is the opportunity
        # we want analytics to surface).
        for rule in AFFINITIES:
            if rule.antecedent in basket and rule.consequent not in basket:
                if rng.random() < rule.cooccurrence_probability:
                    basket.add(rule.consequent)
    return list(basket)


def _quantity_for_product(product_id: str, rng: random.Random) -> int:
    '''
        Sensible quantity ranges per category.
    '''
    if product_id.startswith('SKU-A'):  # galletas
        return rng.randint(6, 24)
    if product_id.startswith('SKU-B'):  # yogurts
        return rng.randint(4, 12)
    if product_id.startswith('SKU-C'):  # cerveza
        return rng.randint(2, 8)
    if product_id.startswith('SKU-D'):  # snacks
        return rng.randint(6, 18)
    return rng.randint(3, 10)


def synthesize(num_orders: int, start_date: date, days: int,
               seed: int) -> pd.DataFrame:
    '''
        Returns a DataFrame matching `template_ventas_v1.xlsx`.
    '''
    rng = random.Random(seed)
    rows = []
    order_counter = 1
    for _ in range(num_orders):
        pdv = rng.choice(PDVS)
        order_date = start_date + timedelta(days = rng.randint(0, days - 1))
        basket = _basket_for_pdv(pdv['id_punto_venta'], rng)
        order_id = f'P-{order_counter:05d}'
        for product_id in basket:
            product = PRODUCT_BY_ID[product_id]
            quantity = _quantity_for_product(product_id, rng)
            rows.append({
                'id_pedido': order_id,
                'fecha': order_date,
                'id_punto_venta': pdv['id_punto_venta'],
                'nombre_pdv': pdv['nombre_pdv'],
                'zona': pdv['zona'],
                'id_producto': product_id,
                'nombre_producto': product['nombre_producto'],
                'cantidad': quantity,
                'precio_unitario': product['precio_unitario'],
                'monto_total': round(quantity * product['precio_unitario'], 2),
            })
        order_counter += 1
    return pd.DataFrame(rows)


def write_excel(dataframe: pd.DataFrame, output_path: Path) -> None:
    '''
        Materializes the dataframe as a .xlsx with the v1 template column order.
    '''
    output_path.parent.mkdir(parents = True, exist_ok = True)
    columns = [
        'id_pedido', 'fecha', 'id_punto_venta', 'nombre_pdv', 'zona',
        'id_producto', 'nombre_producto', 'cantidad', 'precio_unitario',
        'monto_total',
    ]
    with pd.ExcelWriter(output_path, engine = 'openpyxl') as writer:
        dataframe[columns].to_excel(writer, sheet_name = 'Ventas', index = False)
        worksheet = writer.sheets['Ventas']
        for column_cells in worksheet.columns:
            max_length = max(
                (len(str(cell.value or '')) for cell in column_cells), default = 12
            )
            worksheet.column_dimensions[column_cells[0].column_letter].width = (
                min(max_length + 2, 28)
            )


def _print_quick_stats(dataframe: pd.DataFrame) -> None:
    '''
        Prints a one-shot summary so the demo runner can sanity-check the file
        before showing it to a prospect.
    '''
    print('--- Synthetic dataset stats ---')
    print(f'  rows                    : {len(dataframe)}')
    print(f'  unique orders           : {dataframe["id_pedido"].nunique()}')
    print(f'  unique PdVs             : {dataframe["id_punto_venta"].nunique()}')
    print(f'  unique products         : {dataframe["id_producto"].nunique()}')
    print(f'  date range              : '
          f'{dataframe["fecha"].min()} → {dataframe["fecha"].max()}')
    print(f'  total monto             : {dataframe["monto_total"].sum():,.2f}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description = 'Generate a synthetic sales Excel for the SmartDecisions POC.'
    )
    parser.add_argument(
        '--output', type = Path,
        default = Path('tools/samples/ventas_demo.xlsx'),
        help = 'Output .xlsx path.'
    )
    parser.add_argument('--orders', type = int, default = 1200,
                        help = 'Total number of orders to synthesize.')
    parser.add_argument('--days', type = int, default = 60,
                        help = 'How many days the orders span.')
    parser.add_argument('--start', type = str, default = '2026-04-01',
                        help = 'First date (YYYY-MM-DD).')
    parser.add_argument('--seed', type = int, default = 42,
                        help = 'Random seed for reproducibility.')
    args = parser.parse_args()

    start_date = date.fromisoformat(args.start)
    dataframe = synthesize(
        num_orders = args.orders,
        start_date = start_date,
        days = args.days,
        seed = args.seed
    )
    write_excel(dataframe, args.output)
    _print_quick_stats(dataframe)
    print(f'  output                  : {args.output}')
