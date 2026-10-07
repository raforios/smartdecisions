'''
    The history of the sample file: client lifecycles and the months that
    extend the real export backwards.

    A real book of business gains clients, loses others and sees some go quiet
    and come back; and a two-year file needs months the export does not have.
    Both are drawn here from the real months, with trend, seasonality and
    noise, so the analyses have movement to report. Split out of
    `build_sample_dataset.py`, which loads, anonymizes and writes the file.
'''
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


# Demand index of each calendar month RELATIVE TO JANUARY. The three months
# present in the source (Nov, Dec, Jan) keep their real level: they are
# themselves, and scaling them would double-count their own seasonality.
MONTH_SEASONALITY: dict[int, float] = {
    1: 1.00, 2: 0.88, 3: 0.95, 4: 0.93, 5: 0.98, 6: 1.00,
    7: 1.05, 8: 1.00, 9: 0.97, 10: 1.03, 11: 1.00, 12: 1.00,
}

# Categories that only sell in specific calendar months. Panetón is a
# Christmas product in Bolivia; leaving it flat all year would be the kind of
# detail that costs credibility in front of a commercial manager.
SEASONAL_CATEGORIES: dict[str, set[int]] = {
    'PANETONES': {11, 12},
}

# Compounding month-over-month factors applied backwards from the newest month,
# so older months are smaller and cheaper. Gives Growth and the price-drift KPI
# a real signal to report instead of flat lines.
MONTHLY_GROWTH: float = 0.008
MONTHLY_INFLATION: float = 0.004
DEMAND_NOISE: float = 0.06

# A real book of business is not a fixed roster: it gains clients, loses others,
# and some go quiet and come back. Without this the portfolio-health module has
# nothing to report — every month shows the same clients and zero movement.
LIFECYCLE_MIX: dict[str, float] = {
    'leal': 0.60,        # buys across the whole period
    'nuevo': 0.18,       # joins partway through (acquisition)
    'perdido': 0.09,     # stops buying partway through (churn)
    'recuperado': 0.13,  # goes dormant for a stretch, then returns
}

# Probability that an active client places an order in a given month.
# Calibrated against the source export, where 82% of the clients active in one
# month are still active the next (18-20% month-over-month churn). Guessing here
# is what produced first a 6% churn and then a 37% one, neither of them real.
ACTIVITY_RANGE: tuple[float, float] = (0.74, 0.90)

# Each client's own month-over-month multiplier: some grow, some fade. This is
# what produces partial declines in the at-risk list instead of only clients who
# vanished outright.
CLIENT_TREND_RANGE: tuple[float, float] = (0.955, 1.045)

# Months a 'recuperado' client stays dormant before coming back.
DORMANT_SPAN: tuple[int, int] = (2, 4)

# Below this many months a lifecycle cannot be expressed: a churn window and a
# dormant stretch would not fit, and the file would come out nearly empty.
MIN_MONTHS_FOR_LIFECYCLES: int = 8

# Average share of client-months that survive the lifecycle filter. Used to size
# the client pool so `--rows` still lands near the requested figure.
EXPECTED_ACTIVITY: float = 0.74


@dataclass(frozen = True)
class ClientLifecycle:
    '''
        When a client is on the books, how often they buy and whether their
        spend is growing or fading.
    '''
    first: int                                  # first month index on the books
    last: int                                   # last month index, inclusive
    activity: float                             # chance of buying in a month
    trend: float                                # monthly multiplier on spend
    dormant: tuple[int, int] | None = None      # silent stretch, then a return

    def is_on_books(
        self,
        month: int
    ) -> bool:
        '''
            Reports whether the client is expected to buy in a given month.

            Args:
                month (int): Month index within the generated history.

            Returns:
                bool: True when the client is active and not dormant.
        '''
        if not self.first <= month <= self.last:
            return False
        if self.dormant and self.dormant[0] <= month <= self.dormant[1]:
            return False
        return True


def _draw_lifecycle(
    kind: str,
    months: int,
    rng: np.random.Generator
) -> ClientLifecycle:
    '''
        Builds one client's lifecycle from its behavioural class.

        Args:
            kind (str): One of the LIFECYCLE_MIX keys.
            months (int): Length of the generated history.
            rng: Seeded numpy generator.

        Returns:
            ClientLifecycle: The client's window, cadence and trend.
    '''
    activity = float(rng.uniform(*ACTIVITY_RANGE))
    trend = float(rng.uniform(*CLIENT_TREND_RANGE))
    last = months - 1

    # A short history has no room for a join, a churn and a dormant stretch
    # without emptying the file; everyone simply stays on the books.
    if months < MIN_MONTHS_FOR_LIFECYCLES:
        return ClientLifecycle(0, last, activity, trend)

    if kind == 'nuevo':
        return ClientLifecycle(int(rng.integers(1, months - 1)), last, activity, trend)
    if kind == 'perdido':
        # Churn happens in the recent half so the loss is visible in the
        # report, without leaving a long tail of clients gone for two years.
        return ClientLifecycle(0, int(rng.integers(months // 2, months - 2)), activity, trend)
    if kind == 'recuperado':
        start = int(rng.integers(2, max(months - DORMANT_SPAN[1] - 2, 3)))
        span = int(rng.integers(*DORMANT_SPAN))
        return ClientLifecycle(0, last, activity, trend, (start, start + span))
    return ClientLifecycle(0, last, activity, trend)


def build_lifecycles(
    clients: np.ndarray,
    months: int,
    rng: np.random.Generator
) -> dict[Any, ClientLifecycle]:
    '''
        Assigns every client a behavioural class and its resulting lifecycle.

        Args:
            clients (np.ndarray): Client identifiers.
            months (int): Length of the generated history.
            rng: Seeded numpy generator.

        Returns:
            dict: Lifecycle per client id.
    '''
    kinds = list(LIFECYCLE_MIX)
    weights = np.array([LIFECYCLE_MIX[kind] for kind in kinds])
    drawn = rng.choice(kinds, size = len(clients), p = weights / weights.sum())
    return {
        client: _draw_lifecycle(kind, months, rng)
        for client, kind in zip(clients, drawn)
    }


def _buyers_of_month(
    lifecycles: dict[Any, ClientLifecycle],
    month: int,
    rng: np.random.Generator,
    draw_cadence: bool = True
) -> set:
    '''
        Selects which clients order in a given month.

        `draw_cadence` is False for the real months: those already carry the
        source file's own roster, where clients naturally skip months. Drawing a
        cadence on top of it would stack two sources of absence and report a
        churn far above the 18-20% the real data actually shows.

        Args:
            lifecycles (dict): Lifecycle per client id.
            month (int): Month index within the generated history.
            rng: Seeded numpy generator.
            draw_cadence (bool): Whether to also draw the monthly purchase odds.

        Returns:
            set: Client ids buying that month.
    '''
    return {
        client for client, life in lifecycles.items()
        if life.is_on_books(month) and (not draw_cadence or rng.random() < life.activity)
    }


def _apply_client_trend(
    block: pd.DataFrame,
    lifecycles: dict[Any, ClientLifecycle],
    month: int
) -> pd.DataFrame:
    '''
        Scales each client's quantities by their own trajectory, so a declining
        client declines everywhere and shows up in the at-risk list for the
        right reason.

        Args:
            block (pd.DataFrame): Rows of one month.
            lifecycles (dict): Lifecycle per client id.
            month (int): Month index within the generated history.

        Returns:
            pd.DataFrame: The block with per-client trend applied.
    '''
    factors = block['cliente_id'].map(
        lambda client: lifecycles[client].trend ** max(month - lifecycles[client].first, 0)
    )
    block['cantidad'] = np.maximum(np.round(block['cantidad'] * factors), 1)
    return block


def _source_period(
    target: pd.Period,
    real: list[pd.Period]
) -> pd.Period:
    '''
        Chooses which real month a synthesized month is cloned from: the one
        with the same calendar month when it exists (so November keeps its real
        November shape), otherwise the most recent ordinary month.

        Args:
            target (pd.Period): Month being generated.
            real (list[pd.Period]): Real months available, ascending.

        Returns:
            pd.Period: The month to clone.
    '''
    for period in real:
        if period.month == target.month:
            return period
    return real[-1]


def _shift_to_period(
    dates: pd.Series,
    target: pd.Period
) -> pd.Series:
    '''
        Moves dates into the target month keeping the day of month, clamped to
        the target month's length.

        Args:
            dates (pd.Series): Source datetimes.
            target (pd.Period): Destination month.

        Returns:
            pd.Series: Datetimes inside the target month.
    '''
    last_day = target.days_in_month
    days = dates.dt.day.clip(upper = last_day)
    return pd.to_datetime(
        {'year': target.year, 'month': target.month, 'day': days}
    )


def _drop_out_of_season(
    block: pd.DataFrame,
    month: int
) -> pd.DataFrame:
    '''
        Removes rows of a strictly seasonal category from a month where that
        category does not sell (panetón outside Christmas, for instance).

        Args:
            block (pd.DataFrame): Rows cloned into the target month.
            month (int): Calendar month being generated (1-12).

        Returns:
            pd.DataFrame: Rows that belong in that month.
    '''
    out_of_season = block['categoria'].isin([
        category for category, months in SEASONAL_CATEGORIES.items()
        if month not in months
    ])
    return block[~out_of_season].copy()


def _scale_block(
    block: pd.DataFrame,
    factors: tuple[float, float],
    rng: np.random.Generator
) -> pd.DataFrame:
    '''
        Applies the demand and price factors of a synthesized month.

        Args:
            block (pd.DataFrame): Rows cloned from a real month.
            factors (tuple[float, float]): (demand, price) multipliers.
            rng: Seeded numpy generator for the per-line demand noise.

        Returns:
            pd.DataFrame: Scaled rows.
    '''
    demand, price = factors
    noise = rng.normal(1.0, DEMAND_NOISE, len(block))
    block['cantidad'] = np.maximum(np.round(block['cantidad'] * demand * noise), 1)
    block['precio_unitario'] = block['precio_unitario'] * price
    return block


def extend_history(
    frame: pd.DataFrame,
    months: int,
    seed: int
) -> pd.DataFrame:
    '''
        Extends the real months backwards into a `months`-long history by
        cloning each real month and applying trend, seasonality and noise.

        Real months are emitted untouched: they already carry their own
        seasonality, and rescaling them would count it twice.

        Args:
            frame (pd.DataFrame): Anonymized frame carrying 'precio_unitario'.
            months (int): Length of the history, in months.
            seed (int): Seed of the build.

        Returns:
            pd.DataFrame: Frame spanning `months` months.
    '''
    rng = np.random.default_rng(seed + 1)
    real = sorted(frame['periodo'].unique())
    targets = pd.period_range(end = real[-1], periods = months, freq = 'M')
    lifecycles = build_lifecycles(frame['cliente_id'].unique(), months, rng)

    blocks: list[pd.DataFrame] = []
    for offset, target in enumerate(targets):
        age = len(targets) - 1 - offset  # months back from the newest month
        block = frame[frame['periodo'] == _source_period(target, real)].copy()
        # Membership (joins, churns, dormancy) applies to every month so the
        # movement is continuous; only the synthesized months also need a drawn
        # cadence, since they clone one real month's roster over and over.
        buyers = _buyers_of_month(lifecycles, offset, rng, draw_cadence = target not in real)
        block = block[block['cliente_id'].isin(buyers)]
        if block.empty:
            continue

        if target not in real:
            block = _drop_out_of_season(block, target.month)
            block['fecha'] = _shift_to_period(block['fecha'], target)
            block['periodo'] = target
            demand = MONTH_SEASONALITY[target.month] / (1 + MONTHLY_GROWTH) ** age
            block = _scale_block(block, (demand, 1 / (1 + MONTHLY_INFLATION) ** age), rng)

        blocks.append(_apply_client_trend(block, lifecycles, offset))

    history = pd.concat(blocks, ignore_index = True)
    return history.sort_values('fecha').reset_index(drop = True)
