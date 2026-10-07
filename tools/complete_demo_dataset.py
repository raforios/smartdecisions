'''
    Completes a template-shaped sales file into the five files of a full demo.

    The two demo companies are ours: their names are invented and the data was
    built on examples we were given. A demo company is the scenario a client
    should aim for, so it carries every file the product reads — sales with
    cost and credit terms, collections, stock, visits and objectives.

    `build_sample_dataset` already does this for the file it builds itself
    (Comercial Illimani). This tool runs the same generators over a file that
    came from elsewhere — `convert_sales_export` over `base 2025.xlsx`
    (Distribuidora Andina) — so both companies are complete in the same way:

        1. Unit cost, from the per-category margins of `build_sample_dataset`,
           drawn once per product. Only where the file has no cost (empty or
           zero): a real cost is never overwritten.
        2. Credit terms and the collections sheet (`build_receivables`).
        3. The stock photo of the last day (`build_receivables`).
        4. The visit log of the last weeks (`build_visits`).
        5. Monthly objectives per client (`derive_objectives`).

    Everything is seeded, so the same input always yields the same files.

    `--end-date` moves every date of the sales so the last one falls on that
    day (or the closest earlier one keeping the weekday): a demo whose data
    ends yesterday shows a current portfolio and crosses the exchange rate
    float of 27-jun-2026.

    Usage:
        python -m tools.complete_demo_dataset ventas.xlsx --out-dir /tmp/andina
        python -m tools.complete_demo_dataset ventas.xlsx --out-dir /tmp/andina \
            --end-date 2026-10-04
'''
import argparse
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from tools.build_receivables import build_credit_book, build_stock_snapshot
from tools.build_sample_dataset import CATEGORY_MARGINS, DEFAULT_MARGIN, MARGIN_JITTER
from tools.build_visits import build_visits_sheet
from tools.derive_objectives import DEFAULT_ATTAINMENT_RATE, derive

DATE_COLUMNS = ('Fecha', 'Fecha Vencimiento')
PRODUCT = 'Producto'
CATEGORY = 'Categoria'
PRICE = 'Precio Unitario'
COST = 'Costo Unitario'
DEFAULT_SEED = 20261004


def fill_unit_cost(
    sales: pd.DataFrame,
    seed: int
) -> pd.DataFrame:
    '''
        Fills the unit cost where the file left it empty or at zero.

        Args:
            sales (pd.DataFrame): Rows of the sales template.
            seed (int): Seed making the per-product margin reproducible.

        Returns:
            pd.DataFrame: The same rows, every one with a positive cost.
    '''
    rng = np.random.default_rng(seed)
    frame = sales.copy()
    catalog = frame[[PRODUCT, CATEGORY]].drop_duplicates(PRODUCT)
    jitter = rng.uniform(-MARGIN_JITTER, MARGIN_JITTER, len(catalog))
    base = catalog[CATEGORY].str.upper().map(CATEGORY_MARGINS).fillna(DEFAULT_MARGIN)
    margins = dict(zip(catalog[PRODUCT], np.clip(base + jitter, 0.05, 0.60)))

    cost = pd.to_numeric(frame[COST], errors = 'coerce')
    missing = cost.isna() | (cost <= 0)
    derived = frame[PRICE] * (1 - frame[PRODUCT].map(margins))
    frame[COST] = cost.where(~missing, derived.round(4))
    return frame


def shift_dates(
    sales: pd.DataFrame,
    end_date: date
) -> pd.DataFrame:
    '''
        Moves every date by whole weeks so the last sale falls on `end_date`
        or the closest earlier day with the same weekday.

        Args:
            sales (pd.DataFrame): Rows of the sales template.
            end_date (date): Where the data should end.

        Returns:
            pd.DataFrame: The same rows, dated later.
    '''
    frame = sales.copy()
    last = pd.to_datetime(frame['Fecha']).max().date()
    weeks = (end_date - last).days // 7
    delta = pd.Timedelta(weeks = weeks)
    for column in DATE_COLUMNS:
        if column in frame.columns:
            frame[column] = pd.to_datetime(frame[column], errors = 'coerce') + delta
    return frame


def main(argument_list: list | None = None) -> int:
    '''
        Entry point.

        Args:
            argument_list (list): Arguments, for tests. Defaults to argv.

        Returns:
            int: Process exit code.
    '''
    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument('sales', help = 'A file with the sales template.')
    parser.add_argument('--out-dir', required = True, help = 'Where to write the five files.')
    parser.add_argument('--seed', type = int, default = DEFAULT_SEED)
    parser.add_argument('--scenario', default = 'estresada', help = 'Credit scenario.')
    parser.add_argument('--stock-scenario', default = 'ajustado', help = 'Stock scenario.')
    parser.add_argument('--end-date', default = None,
                        help = 'Move the dates so the data ends this day (YYYY-MM-DD).')
    arguments = parser.parse_args(argument_list)

    out_dir = Path(arguments.out_dir)
    out_dir.mkdir(parents = True, exist_ok = True)

    sales = fill_unit_cost(pd.read_excel(arguments.sales), arguments.seed)
    if arguments.end_date:
        sales = shift_dates(sales, date.fromisoformat(arguments.end_date))
    book = build_credit_book(sales, arguments.scenario, arguments.seed)
    files = {
        'ventas': book.sales,
        'cobros': book.collections,
        'stock': build_stock_snapshot(book.sales, arguments.stock_scenario, arguments.seed),
        'visitas': build_visits_sheet(book.sales, arguments.seed),
        'objetivos': derive(book.sales, DEFAULT_ATTAINMENT_RATE),
    }
    for name, frame in files.items():
        destination = out_dir / f'{name}.xlsx'
        frame.to_excel(destination, index = False, sheet_name = 'Datos')
        print(f'{name:10} {len(frame):6} filas -> {destination}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
