'''
    Credit book generator for the demo dataset.

    The sales export we build the sample from is 99,9% cash: 121.128 rows
    "Contado" against 95 "Crédito". The prospects who asked for the receivables
    module described the opposite — around 70% of their sales on credit, with
    terms from 5 to 120 days — so the credit book cannot be *derived* from the
    source file. It is generated here, explicitly and deterministically, and the
    workbook says so on its provenance sheet.

    What it produces, on top of the sales sheet:
        * The credit columns of the sales contract: condition, term, due date,
          collector and the client's credit limit.
        * The `Cobros` sheet: one row per payment, several per invoice when it
          was collected in instalments.

    Three scenarios, because a dashboard that only ever shows a healthy book
    proves nothing: `sana`, `estresada` and `crisis` differ only in how the
    payment behaviour is drawn.

    Everything is drawn from a seeded generator, so the same scenario always
    produces the same book and a demo can be rehearsed.
'''
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

# The sheet names are part of the microservice's contract and not a decision of
# this tool: they are read from there so the two cannot diverge.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'services' / 'ingest'))
from schemas.ingest import COLLECTIONS_SHEET, STOCK_SHEET   # noqa: E402  pylint: disable=wrong-import-position

# Terms seen in the Bolivian mass-consumption market, with the weight of each.
# The 5- and 15-day ones belong to corner shops; 90 and 120, to chains.
TERM_DAYS: Tuple[int, ...] = (5, 15, 30, 45, 60, 90, 120)
TERM_WEIGHTS: Tuple[float, ...] = (0.08, 0.20, 0.34, 0.14, 0.14, 0.07, 0.03)

# Payment methods, so the column is not empty in the demo.
PAYMENT_METHODS: Tuple[str, ...] = ('EFECTIVO', 'TRANSFERENCIA', 'CHEQUE', 'QR')
METHOD_WEIGHTS: Tuple[float, ...] = (0.46, 0.34, 0.08, 0.12)

# Payment behaviours. Each scenario's weights add up to 1.
BEHAVIOURS: Tuple[str, ...] = ('ON_TIME', 'LATE', 'VERY_LATE', 'PARTIAL', 'UNPAID')

SCENARIOS: Dict[str, Tuple[float, ...]] = {
    # Healthy book: collected on time, with marginal delinquency.
    'sana': (0.70, 0.18, 0.05, 0.05, 0.02),
    # Stressed book: delinquency weighs and some balances never come back.
    'estresada': (0.45, 0.27, 0.13, 0.10, 0.05),
    # Book in crisis: over a third overdue and a visible write-off.
    'crisis': (0.28, 0.27, 0.22, 0.12, 0.11),
}

# How much of the sales goes on credit. It is what the prospects described.
CREDIT_SHARE: float = 0.70
# A large invoice is likelier to go on credit: the wholesaler buys volume and
# finances it, while the corner shop pays on the spot. The factor is applied on
# both sides of the median so the overall share stays at CREDIT_SHARE: raising
# only the large ones left the book at 79% instead of 70%.
LARGE_INVOICE_BOOST: float = 1.15
SMALL_INVOICE_DAMPER: float = 0.85
# Credit limit: a multiple of the client's average monthly purchase, rounded to
# hundreds, with a floor so nobody ends up at zero.
CREDIT_LIMIT_MULTIPLE: float = 2.5
CREDIT_LIMIT_FLOOR: float = 500.0


@dataclass(frozen = True)
class CreditBook:
    '''
        The two sheets of a credit book: the sales with their terms and the
        payments that were collected against them.
    '''
    sales: pd.DataFrame
    collections: pd.DataFrame
    scenario: str
    as_of: pd.Timestamp


def _credit_flags(invoices: pd.DataFrame, rng: np.random.Generator) -> np.ndarray:
    '''
        Decides which invoices went on credit.

        Args:
            invoices (pd.DataFrame): One row per invoice, with its amount.
            rng (np.random.Generator): Seeded generator.

        Returns:
            np.ndarray: Boolean mask aligned to `invoices`.
    '''
    median = float(invoices['amount'].median())
    factor = np.where(
        invoices['amount'] > median, LARGE_INVOICE_BOOST, SMALL_INVOICE_DAMPER
    )
    probability = np.clip(CREDIT_SHARE * factor, 0.0, 0.98)
    return rng.random(len(invoices)) < probability


def _payment_rows(invoice: Dict[str, Any], behaviour: str,
                  rng: np.random.Generator, as_of: pd.Timestamp) -> List[Dict[str, Any]]:
    '''
        Builds the payment rows of one credit invoice.

        A payment dated after the cut-off has simply not happened yet, so it is
        dropped and the invoice stays open. That is what makes the aging honest:
        a recent invoice is open and current, an old one is open and overdue.

        Args:
            invoice (Dict[str, Any]): Invoice number, amount, due date, collector.
            behaviour (str): One of BEHAVIOURS.
            rng (np.random.Generator): Seeded generator.
            as_of (pd.Timestamp): The book's cut-off date.

        Returns:
            List[Dict[str, Any]]: Payment rows, possibly empty.
    '''
    if behaviour == 'UNPAID':
        return []

    due = invoice['due_date']
    total = float(invoice['amount'])

    if behaviour == 'ON_TIME':
        # Paid within the term: between five days early and the due date.
        paid_on = due - pd.Timedelta(days = int(rng.integers(0, 6)))
        instalments = [(paid_on, total)]
    elif behaviour == 'LATE':
        paid_on = due + pd.Timedelta(days = int(rng.integers(1, 31)))
        instalments = [(paid_on, total)]
    elif behaviour == 'VERY_LATE':
        paid_on = due + pd.Timedelta(days = int(rng.integers(31, 121)))
        instalments = [(paid_on, total)]
    else:
        # Partial: one instalment on or near the due date, the rest uncollected.
        share = float(rng.uniform(0.3, 0.7))
        paid_on = due + pd.Timedelta(days = int(rng.integers(-3, 20)))
        instalments = [(paid_on, round(total * share, 2))]

    method = PAYMENT_METHODS[int(rng.choice(len(PAYMENT_METHODS), p = METHOD_WEIGHTS))]
    return [
        {
            'Nro Factura': invoice['order_id'],
            'Fecha Cobro': date.date(),
            'Monto Cobrado': amount,
            'Medio': method,
            'Responsable Cobro': invoice['collector'],
        }
        for date, amount in instalments
        if date <= as_of
    ]


def _invoice_table(sheet: pd.DataFrame) -> pd.DataFrame:
    '''
        Collapses the sales sheet into one row per invoice.

        The receivable lives at invoice level: in the sales sheet an invoice
        spans one row per product line, and a payment is imputed against the
        whole document.

        Args:
            sheet (pd.DataFrame): Template-shaped sales sheet.

        Returns:
            pd.DataFrame: Invoice number, date, client, seller and total.
    '''
    frame = sheet.copy()
    frame['Fecha'] = pd.to_datetime(frame['Fecha'])
    return frame.groupby('Nro Factura', as_index = False).agg(
        date = ('Fecha', 'min'),
        client = ('Cliente', 'first'),
        collector = ('Vendedor', 'first'),
        amount = ('Monto Total', 'sum')
    ).rename(columns = {'Nro Factura': 'order_id'})


def _credit_limits(invoices: pd.DataFrame) -> pd.Series:
    '''
        A credit limit per client, from their own monthly purchase.

        Args:
            invoices (pd.DataFrame): One row per invoice.

        Returns:
            pd.Series: Limit per client name.
    '''
    months = invoices.assign(month = invoices['date'].dt.to_period('M'))
    monthly = months.groupby(['client', 'month'])['amount'].sum()
    average = monthly.groupby('client').mean()
    limits = (average * CREDIT_LIMIT_MULTIPLE / 100).round() * 100
    return limits.clip(lower = CREDIT_LIMIT_FLOOR)


def build_credit_book(sheet: pd.DataFrame, scenario: str, seed: int) -> CreditBook:
    '''
        Adds the credit columns to a sales sheet and builds its payments sheet.

        Args:
            sheet (pd.DataFrame): Template-shaped sales sheet ('Ventas').
            scenario (str): One of SCENARIOS.
            seed (int): Seed, so the same scenario always yields the same book.

        Returns:
            CreditBook: The sales sheet with its credit columns and the
                payments sheet.

        Raises:
            KeyError: If the scenario is not one of SCENARIOS.
    '''
    weights = SCENARIOS[scenario]
    rng = np.random.default_rng(seed)

    invoices = _invoice_table(sheet)
    invoices['is_credit'] = _credit_flags(invoices, rng)
    invoices['term'] = np.where(
        invoices['is_credit'],
        rng.choice(TERM_DAYS, size = len(invoices), p = TERM_WEIGHTS),
        0
    )
    invoices['due_date'] = invoices['date'] + pd.to_timedelta(invoices['term'], unit = 'D')
    invoices['behaviour'] = np.where(
        invoices['is_credit'],
        rng.choice(BEHAVIOURS, size = len(invoices), p = weights),
        'ON_TIME'
    )

    # The cut-off is the last day with activity in the file: the photo is taken
    # where the data ends and not the day the script runs, or the whole book
    # would look overdue only because time passed.
    as_of = invoices['date'].max()

    payments: List[Dict[str, Any]] = []
    for invoice in invoices.loc[invoices['is_credit']].to_dict('records'):
        payments.extend(_payment_rows(invoice, invoice['behaviour'], rng, as_of))

    limits = _credit_limits(invoices)
    terms = invoices.set_index('order_id')

    sales = sheet.copy()
    sales['Condicion Venta'] = sales['Nro Factura'].map(
        terms['is_credit'].map({True: 'CREDITO', False: 'CONTADO'})
    )
    sales['Plazo Dias'] = sales['Nro Factura'].map(terms['term']).astype(int)
    sales['Fecha Vencimiento'] = sales['Nro Factura'].map(
        terms['due_date']
    ).dt.date.where(sales['Condicion Venta'] == 'CREDITO')
    sales['Responsable Cobro'] = sales['Vendedor']
    sales['Limite Credito'] = sales['Cliente'].map(limits).round(2)

    collections = pd.DataFrame(
        payments,
        columns = ['Nro Factura', 'Fecha Cobro', 'Monto Cobrado', 'Medio',
                   'Responsable Cobro']
    ).sort_values(['Fecha Cobro', 'Nro Factura']).reset_index(drop = True)

    return CreditBook(
        sales = sales, collections = collections, scenario = scenario, as_of = as_of
    )


def describe(book: CreditBook) -> None:
    '''
        Prints what the generated book looks like, so a bad draw is visible
        before it reaches a demo.

        Args:
            book (CreditBook): The generated book.

        Returns:
            None
    '''
    invoices = book.sales.groupby('Nro Factura').agg(
        amount = ('Monto Total', 'sum'),
        terms = ('Condicion Venta', 'first'),
        due = ('Fecha Vencimiento', 'first')
    )
    credit = invoices.loc[invoices['terms'] == 'CREDITO']
    collected = book.collections.groupby('Nro Factura')['Monto Cobrado'].sum()
    open_balance = credit['amount'] - collected.reindex(credit.index).fillna(0.0)
    overdue = open_balance.loc[
        pd.to_datetime(credit['due'], errors = 'coerce') < book.as_of
    ]

    print(f'  escenario        {book.scenario}')
    print(f'  corte            {book.as_of.date()}')
    print(f'  facturas         {len(invoices):,} · a crédito {len(credit):,} '
          f'({len(credit) / len(invoices) * 100:.0f}% de las facturas, '
          f'{credit["amount"].sum() / invoices["amount"].sum() * 100:.0f}% del monto)')
    print(f'  cobros           {len(book.collections):,} filas · '
          f'Bs {book.collections["Monto Cobrado"].sum():,.0f}')
    print(f'  saldo abierto    Bs {open_balance.clip(lower = 0).sum():,.0f} '
          f'en {int((open_balance > 0.01).sum()):,} facturas')
    print(f'  vencido          Bs {overdue.clip(lower = 0).sum():,.0f}')

# --- Stock of the day ---------------------------------------------------------
# Warehouse scenarios. Each one splits the catalogue into situations: out of
# stock, critical, low, healthy, excess and no demand. A photo where everything
# is healthy proves nothing in a demo.
STOCK_SITUATIONS: Tuple[str, ...] = (
    'OUT', 'CRITICAL', 'LOW', 'HEALTHY', 'EXCESS', 'DEAD'
)

STOCK_SCENARIOS: Dict[str, Tuple[float, ...]] = {
    'sano': (0.01, 0.04, 0.10, 0.65, 0.15, 0.05),
    'ajustado': (0.05, 0.12, 0.20, 0.45, 0.13, 0.05),
    'critico': (0.12, 0.20, 0.22, 0.30, 0.10, 0.06),
}

# Days of coverage given to each situation, so the photo falls on the right
# side of the thresholds the engine reads.
COVERAGE_BY_SITUATION: Dict[str, Tuple[float, float]] = {
    'OUT': (0.0, 0.0),
    'CRITICAL': (1.0, 6.0),
    'LOW': (8.0, 14.0),
    'HEALTHY': (20.0, 70.0),
    'EXCESS': (110.0, 220.0),
    'DEAD': (0.0, 0.0),
}

# Share of the balance the ERP already committed in orders. It is READ, never
# written: the dashboard reflects a decision the ERP took.
COMMITTED_SHARE: Tuple[float, float] = (0.0, 0.25)


def build_stock_snapshot(sheet: pd.DataFrame, scenario: str, seed: int,
                         window_days: int = 90) -> pd.DataFrame:
    '''
        Builds the stock snapshot of the last day of the sales sheet.

        The stock is drawn FROM the observed demand: a product selling 10 units
        a day gets the units its situation calls for at that pace. Drawing a
        balance at random would produce coverages nobody can read — a product
        with 5.000 units and no sales, or a best-seller with three.

        The snapshot is dated on the last day of the file and not today, so the
        analysis matches the rest of the dataset.

        Args:
            sheet (pd.DataFrame): Template-shaped sales sheet.
            scenario (str): One of STOCK_SCENARIOS.
            seed (int): Seed, so the same scenario always yields the same photo.
            window_days (int): Window the daily demand is measured over; must
                match STOCK_DEMAND_WINDOW_DAYS of ANALYTICS.

        Returns:
            pd.DataFrame: The 'Stock' sheet.

        Raises:
            KeyError: If the scenario is not one of STOCK_SCENARIOS.
    '''
    weights = STOCK_SCENARIOS[scenario]
    rng = np.random.default_rng(seed + 1)

    frame = sheet.copy()
    frame['Fecha'] = pd.to_datetime(frame['Fecha'])
    as_of = frame['Fecha'].max()
    window = frame.loc[frame['Fecha'] > as_of - pd.Timedelta(days = window_days)]

    span = max((as_of - window['Fecha'].min()).days + 1, 1)
    demand = window.groupby('Producto')['Cantidad'].sum() / span
    catalogue = frame.groupby('Producto').agg(
        cost = ('Costo Unitario', 'mean')
    )
    catalogue['demand'] = demand.reindex(catalogue.index).fillna(0.0)

    situations = rng.choice(STOCK_SITUATIONS, size = len(catalogue), p = weights)
    rows: List[Dict[str, Any]] = []

    for (product, row), situation in zip(catalogue.iterrows(), situations):
        daily = float(row['demand'])
        low, high = COVERAGE_BY_SITUATION[situation]

        if situation == 'OUT':
            on_hand = 0.0
        elif situation == 'DEAD' or daily <= 0:
            # Idle capital: units with no measured demand moving them.
            on_hand = float(rng.integers(20, 400))
        else:
            on_hand = round(daily * float(rng.uniform(low, high)), 0)

        committed = round(on_hand * float(rng.uniform(*COMMITTED_SHARE)), 0)
        rows.append({
            'Fecha': as_of.date(),
            'Producto': product,
            'Existencia': on_hand,
            'Comprometido': committed,
            'En Transito': round(on_hand * float(rng.uniform(0.0, 0.3)), 0),
            'Almacen': 'Central',
            'Costo Unitario': round(float(row['cost']), 2),
        })

    return pd.DataFrame(rows)


def describe_stock(snapshot: pd.DataFrame, scenario: str) -> None:
    '''
        Prints what the snapshot looks like, so a bad draw is visible before it
        reaches a demo.

        Args:
            snapshot (pd.DataFrame): The generated 'Stock' sheet.
            scenario (str): Scenario it was drawn with.

        Returns:
            None
    '''
    value = (snapshot['Existencia'] * snapshot['Costo Unitario']).sum()
    empty = int((snapshot['Existencia'] <= 0).sum())
    print(f'  stock            escenario {scenario} · {len(snapshot)} productos · '
          f'{empty} sin existencia')
    print(f'  valorizado       Bs {value:,.0f} · comprometido '
          f'{snapshot["Comprometido"].sum():,.0f} unidades')
