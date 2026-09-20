'''
    Synthetic visits for the demo workbook.

    The source export has no visit log —it is a sales ledger— so the executed
    side of the routes is drawn FROM the sales: a seller who invoiced a client
    on a given day was there. That is the honest core. Around it, the draw adds
    what a real week has and a ledger never shows: calls that ended without a
    sale, a closed shop, a client not found, and a few sales taken by phone with
    nobody at the door. Hours follow a nearest-neighbour walk from the first
    stop, so the order on the street is a plausible order and not the invoice
    sequence; coordinates get the jitter of a phone GPS and some rows lose them,
    because that is what the client's file will look like.

    Only the last weeks of the ledger are covered: a visit log is exported
    week by week, and eight weeks is what a demo needs to compare a plan with
    its execution.

    Usage from the dataset builder:

        from tools.build_visits import build_visits_sheet, describe_visits
'''
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services' / 'ingest'))
from schemas.ingest import VISITS_SHEET   # noqa: E402  pylint: disable=wrong-import-position

# What a week on the street looks like, as shares of the visits drawn.
_OFF_PLAN_SHARE = 0.18      # calls to clients that did not buy that day
_PHONE_SALE_SHARE = 0.05    # sales with no visit behind them
_NO_GEO_SHARE = 0.15        # rows the client's system exported without GPS
_NO_OUTCOME_SHARE = 0.10    # rows without a result code
_OFF_PLAN_OUTCOMES = ('SIN_VENTA', 'SIN_VENTA', 'CERRADO', 'NO_ENCONTRADO')
_GPS_JITTER_DEGREES = 0.0003  # about thirty metres
_FIRST_STOP_MINUTES = 8 * 60 + 30
_MINUTES_PER_STOP = (18, 35)


def _walk_order(points: np.ndarray, rng: np.random.Generator) -> list[int]:
    '''
        Orders the stops of a day the way a seller drives them: from a random
        first stop, always to the nearest one not yet visited.

        Args:
            points (np.ndarray): Latitude/longitude pairs; NaN when unknown.
            rng (np.random.Generator): Seeded generator.

        Returns:
            list[int]: Row positions in visiting order.
    '''
    count = len(points)
    if count <= 1:
        return list(range(count))
    known = ~np.isnan(points).any(axis = 1)
    remaining = [index for index in range(count) if known[index]]
    unknown = [index for index in range(count) if not known[index]]
    if not remaining:
        return unknown
    order = [remaining.pop(int(rng.integers(len(remaining))))]
    while remaining:
        last = points[order[-1]]
        distances = [np.hypot(*(points[index] - last)) for index in remaining]
        order.append(remaining.pop(int(np.argmin(distances))))
    # Stops without coordinates cannot be placed on the walk: they go last.
    return order + unknown


def _day_visits(day_sales: pd.DataFrame, pool: pd.DataFrame,
                rng: np.random.Generator) -> pd.DataFrame:
    '''
        Draws the visits of one seller on one day.

        Args:
            day_sales (pd.DataFrame): Invoices of that seller that day, one row
                per invoice with the client's coordinates.
            pool (pd.DataFrame): Clients of that seller in the period, to draw
                the off-plan calls from.
            rng (np.random.Generator): Seeded generator.

        Returns:
            pd.DataFrame: Visit rows in the contract's headers.
    '''
    sold = day_sales.copy()
    sold['Resultado'] = 'VENTA'
    # A few sales were taken by phone: the invoice exists, the visit does not.
    sold = sold.loc[rng.random(len(sold)) >= _PHONE_SALE_SHARE]

    others = pool.loc[~pool['Cliente'].isin(day_sales['Cliente'])]
    # The share is kept on days with one or two invoices too: rounding it to
    # zero there would leave a demo of tiny sellers without a single call
    # that ended without a sale.
    expected = len(day_sales) * _OFF_PLAN_SHARE
    extra_count = int(expected) + int(rng.random() < expected - int(expected))
    extra = others.sample(n = min(extra_count, len(others)), random_state = rng.integers(2**31)) \
        if extra_count and len(others) else others.iloc[0:0]
    extra = extra.assign(
        **{'Nro Factura': '',
           'Resultado': rng.choice(_OFF_PLAN_OUTCOMES, size = len(extra))}
    )

    visits = pd.concat([sold, extra], ignore_index = True)
    if visits.empty:
        return visits

    points = visits[['Latitud', 'Longitud']].to_numpy(dtype = float)
    order = _walk_order(points, rng)
    visits = visits.iloc[order].reset_index(drop = True)

    minutes = _FIRST_STOP_MINUTES + np.cumsum(
        rng.integers(_MINUTES_PER_STOP[0], _MINUTES_PER_STOP[1], size = len(visits))
    )
    visits['Hora'] = [f'{m // 60:02d}:{m % 60:02d}' for m in minutes]

    jitter = rng.normal(0, _GPS_JITTER_DEGREES, size = (len(visits), 2))
    visits['Latitud'] = (visits['Latitud'] + jitter[:, 0]).round(6)
    visits['Longitud'] = (visits['Longitud'] + jitter[:, 1]).round(6)
    no_geo = rng.random(len(visits)) < _NO_GEO_SHARE
    visits.loc[no_geo, ['Latitud', 'Longitud']] = np.nan
    no_outcome = rng.random(len(visits)) < _NO_OUTCOME_SHARE
    visits.loc[no_outcome, ['Resultado', 'Nro Factura']] = ''
    return visits


def build_visits_sheet(sales: pd.DataFrame, seed: int, weeks: int = 8) -> pd.DataFrame:
    '''
        Draws the visits sheet from the last weeks of the sales sheet.

        Args:
            sales (pd.DataFrame): Template-shaped sales sheet.
            seed (int): Seed, so the same ledger always yields the same log.
            weeks (int): How many weeks back from the last sale to cover.

        Returns:
            pd.DataFrame: The 'Visitas' sheet, in contract order.
    '''
    rng = np.random.default_rng(seed)
    dates = pd.to_datetime(sales['Fecha'])
    since = dates.max() - pd.Timedelta(weeks = weeks)
    recent = sales.loc[dates >= since].copy()
    recent['Fecha'] = pd.to_datetime(recent['Fecha']).dt.date

    columns = ['Fecha', 'Vendedor', 'Cliente', 'Latitud', 'Longitud', 'Nro Factura']
    invoices = (
        recent.sort_values('Nro Factura')
        .drop_duplicates(subset = ['Fecha', 'Vendedor', 'Cliente'])[columns]
    )
    pools = {
        seller: block.drop_duplicates('Cliente')[['Vendedor', 'Cliente', 'Latitud', 'Longitud']]
        for seller, block in invoices.groupby('Vendedor')
    }

    days = []
    for (day, seller), block in invoices.groupby(['Fecha', 'Vendedor'], sort = True):
        drawn = _day_visits(block, pools[seller], rng)
        drawn['Fecha'] = day
        drawn['Vendedor'] = seller
        days.append(drawn)

    sheet = pd.concat(days, ignore_index = True) if days else pd.DataFrame()
    ordered = ['Fecha', 'Hora', 'Vendedor', 'Cliente', 'Latitud', 'Longitud',
               'Resultado', 'Nro Factura']
    return sheet.reindex(columns = ordered)


def describe_visits(sheet: pd.DataFrame) -> None:
    '''
        Prints what the visit log looks like, so a bad draw is visible before
        it reaches a demo.

        Args:
            sheet (pd.DataFrame): The generated 'Visitas' sheet.

        Returns:
            None
    '''
    outcomes = sheet['Resultado'].replace('', np.nan).value_counts(dropna = False)
    with_geo = int(sheet['Latitud'].notna().sum())
    print(f'  {VISITS_SHEET.lower():<16} {len(sheet)} visitas · '
          f'{sheet["Vendedor"].nunique()} vendedores · '
          f'{sheet["Fecha"].min()} a {sheet["Fecha"].max()}')
    print(f'  con gps          {with_geo} · resultados '
          + ' · '.join(f'{k if isinstance(k, str) else "sin dato"} {v}'
                       for k, v in outcomes.items()))
