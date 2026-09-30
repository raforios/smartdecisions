'''
    Objective attainment: what the company decided, against what happened.

    The arithmetic is deliberately plain, because the value of this block is
    not the calculation — it is that three figures that normally live in three
    different spreadsheets end up on one line. What makes it correct is where
    each figure is measured:

        * `invoiced` is what was billed to the client in THAT month.
        * `collected` is what was paid AGAINST THOSE INVOICES, not what the
          cashier received that month. That is the only reading under which
          invoiced = collected + debt holds, and it is the identity the
          client's own closing workbook is built on.
        * `debt` is the remainder, and it is what separates a client who
          bought from a client who paid.

    Nothing here decides where a percentage stops being acceptable. That cut
    belongs to the account, arrives as its policy, and the service only
    supplies a default when the account never set one.
'''
from typing import Dict, Final, List, Optional, Tuple

import pandas as pd

from schemas.objectives import (
    ClientScoreSchema,
    ClusterCellSchema,
    CommercialPolicySchema,
    ObjectivesBlockSchema,
    ObjectivesTotalsSchema,
    Semaphore
)
from services.environment import load_and_validate_env_vars
from services.logger_config import custom_logger as logger

# Business parameters. Defaults, not constants: the policy of an account
# overrides them one by one, which is how two companies read the same sales
# by their own standards.
_SETTINGS = load_and_validate_env_vars({
    'OBJECTIVES_YELLOW_FROM': float,
    'OBJECTIVES_GREEN_FROM': float,
    'OBJECTIVES_BS_PER_POINT': float,
    'OBJECTIVES_AMOUNT_DECIMALS': int,
    'OBJECTIVES_RATIO_DECIMALS': int,
})

_YELLOW_FROM: Final[float] = _SETTINGS['OBJECTIVES_YELLOW_FROM']
_GREEN_FROM: Final[float] = _SETTINGS['OBJECTIVES_GREEN_FROM']
_BS_PER_POINT: Final[float] = _SETTINGS['OBJECTIVES_BS_PER_POINT']
_AMOUNTS: Final[int] = _SETTINGS['OBJECTIVES_AMOUNT_DECIMALS']
_RATIOS: Final[int] = _SETTINGS['OBJECTIVES_RATIO_DECIMALS']

_POS = 'pos_id'
_PERIOD = 'period'
_TARGET = 'target_amount'
_ORDER = 'order_id'
_AMOUNT = 'total_amount'
_PAID = 'paid_amount'
_DATE = 'date'

# Descriptors carried from the sales rows onto the score, so the matrix can be
# cut by any of them without a second lookup.
_DESCRIPTORS: Final[Tuple[str, ...]] = (
    'pos_name', 'cluster', 'supervisor', 'market', 'channel', 'seller'
)

# What a client with no cluster is grouped under in the matrix. A code and not
# a phrase: the wording belongs to the screen.
_NO_CLUSTER: Final[str] = 'UNASSIGNED'


def resolve_policy(stored: Optional[Dict]) -> CommercialPolicySchema:
    '''
        The yardstick to apply, the account's own where it set one.

        Field by field and not all or nothing: an account that only wants to
        move the green cut should not have to restate the rest.

        Args:
            stored (Dict | None): The policy as persisted, or None.

        Returns:
            CommercialPolicySchema: Every field resolved.
    '''
    saved = stored or {}
    return CommercialPolicySchema(
        yellow_from = _as_float(saved.get('yellow_from'), _YELLOW_FROM),
        green_from = _as_float(saved.get('green_from'), _GREEN_FROM),
        bs_per_point = _as_float(saved.get('bs_per_point'), _BS_PER_POINT),
        points_per_cluster = {
            str(cluster): float(rate)
            for cluster, rate in (saved.get('points_per_cluster') or {}).items()
        }
    )


def _as_float(
    value: object,
    fallback: float
) -> float:
    '''
        A stored number, or the service default when it is absent.

        Args:
            value (object): The stored value, possibly a Decimal or None.
            fallback (float): What to use when nothing was stored.

        Returns:
            float: The resolved number.
    '''
    return float(value) if value is not None else fallback


def _semaphore(
    ratio: float,
    policy: CommercialPolicySchema
) -> Semaphore:
    '''
        How one attainment reads against the account's cuts.

        Args:
            ratio (float): Attainment, as a fraction of the objective.
            policy (CommercialPolicySchema): The resolved policy.

        Returns:
            Semaphore: The code.
    '''
    if ratio >= policy.green_from:
        return Semaphore.GREEN
    return Semaphore.YELLOW if ratio >= policy.yellow_from else Semaphore.RED


def _ratio(
    part: float,
    whole: float
) -> float:
    '''
        A share, with no objective reading as zero rather than dividing.

        Args:
            part (float): The numerator.
            whole (float): The denominator.

        Returns:
            float: The share, rounded.
    '''
    return round(part / whole, _RATIOS) if whole else 0.0


def _points(
    invoiced: float,
    cluster: Optional[str],
    policy: CommercialPolicySchema
) -> float:
    '''
        The points an invoiced amount earns, at the cluster's own rate.

        Args:
            invoiced (float): What was billed.
            cluster (str | None): The client's cluster.
            policy (CommercialPolicySchema): The resolved policy.

        Returns:
            float: The points.
    '''
    rate = (policy.points_per_cluster or {}).get(str(cluster), policy.bs_per_point)
    return round(invoiced / rate, _RATIOS) if rate else 0.0


def _invoiced_by_client_period(sales: pd.DataFrame) -> pd.DataFrame:
    '''
        What each client was billed in each month.

        Args:
            sales (pd.DataFrame): Normalized sales rows.

        Returns:
            pd.DataFrame: Columns pos_id, period, invoiced_amount.
    '''
    frame = sales.loc[:, [_POS, _DATE, _AMOUNT]].copy()
    frame[_PERIOD] = pd.to_datetime(frame[_DATE], errors = 'coerce').dt.strftime('%Y-%m')
    frame = frame.dropna(subset = [_PERIOD])
    grouped = frame.groupby([_POS, _PERIOD], as_index = False)[_AMOUNT].sum()
    return grouped.rename(columns = {_AMOUNT: 'invoiced_amount'})


def _collected_by_client_period(
    sales: pd.DataFrame,
    collections: Optional[pd.DataFrame]
) -> pd.DataFrame:
    '''
        What was paid against each month's invoices.

        The payment is attributed to the month of the INVOICE it settles, not
        to the month it arrived. Any other reading breaks the identity the
        whole block rests on — invoiced = collected + debt — and turns a
        January debt into a February surplus.

        Args:
            sales (pd.DataFrame): Normalized sales rows, carrying the invoice.
            collections (pd.DataFrame | None): Payments, when the account
                loaded them.

        Returns:
            pd.DataFrame: Columns pos_id, period, collected_amount.
    '''
    empty = pd.DataFrame(columns = [_POS, _PERIOD, 'collected_amount'])
    if collections is None or collections.empty or _ORDER not in collections.columns:
        return empty

    invoices = sales.loc[:, [_ORDER, _POS, _DATE]].copy()
    invoices[_PERIOD] = pd.to_datetime(invoices[_DATE], errors = 'coerce').dt.strftime('%Y-%m')
    invoices = invoices.dropna(subset = [_PERIOD]).drop_duplicates(subset = [_ORDER])

    paid = collections.loc[:, [_ORDER, _PAID]].copy()
    paid[_ORDER] = paid[_ORDER].astype(str)
    invoices[_ORDER] = invoices[_ORDER].astype(str)

    married = paid.merge(invoices, on = _ORDER, how = 'inner')
    if married.empty:
        return empty
    grouped = married.groupby([_POS, _PERIOD], as_index = False)[_PAID].sum()
    return grouped.rename(columns = {_PAID: 'collected_amount'})


def _descriptors_of(sales: pd.DataFrame) -> pd.DataFrame:
    '''
        The last known descriptors of each client.

        Args:
            sales (pd.DataFrame): Normalized sales rows.

        Returns:
            pd.DataFrame: One row per client, indexed by pos_id.
    '''
    present = [column for column in _DESCRIPTORS if column in sales.columns]
    if not present:
        return pd.DataFrame(index = pd.Index([], name = _POS))
    frame = sales.loc[:, [_POS, *present]].drop_duplicates(subset = [_POS], keep = 'last')
    return frame.set_index(_POS)


def _score_rows(
    merged: pd.DataFrame,
    policy: CommercialPolicySchema
) -> List[ClientScoreSchema]:
    '''
        Turns the merged figures into one score per client and month.

        Args:
            merged (pd.DataFrame): Objectives with their invoiced, collected
                and descriptor columns.
            policy (CommercialPolicySchema): The resolved policy.

        Returns:
            List[ClientScoreSchema]: The scores.
    '''
    scores: List[ClientScoreSchema] = []
    for row in merged.to_dict('records'):
        target = _amount(row[_TARGET])
        invoiced = _amount(row.get('invoiced_amount'))
        collected = _amount(row.get('collected_amount'))
        invoiced_ratio = _ratio(invoiced, target)
        collected_ratio = _ratio(collected, target)
        scores.append(ClientScoreSchema(
            pos_id = str(row[_POS]),
            period = str(row[_PERIOD]),
            target_amount = round(target, _AMOUNTS),
            invoiced_amount = round(invoiced, _AMOUNTS),
            collected_amount = round(collected, _AMOUNTS),
            debt_amount = round(invoiced - collected, _AMOUNTS),
            invoiced_ratio = invoiced_ratio,
            collected_ratio = collected_ratio,
            invoiced_semaphore = _semaphore(invoiced_ratio, policy),
            collected_semaphore = _semaphore(collected_ratio, policy),
            points = _points(invoiced, row.get('cluster'), policy),
            **{name: _text(row.get(name)) for name in _DESCRIPTORS}
        ))
    return scores


def _amount(value: object) -> float:
    '''
        A merged amount as a number, with a missing match reading as zero.

        Explicit and not `value or 0.0`: a left join fills the gap with NaN,
        and NaN is truthy, so the idiom lets it straight through into the
        arithmetic. That is how a client with an objective and no sales would
        have produced a NaN percentage instead of the zero that is the whole
        reason for loading the objective.

        Args:
            value (object): The cell.

        Returns:
            float: The amount, or zero when there was no match.
    '''
    return 0.0 if value is None or pd.isna(value) else float(value)


def _text(value: object) -> Optional[str]:
    '''
        A descriptor as text, or nothing when the dataset has none.

        Args:
            value (object): The cell.

        Returns:
            str | None: The text.
    '''
    return None if value is None or pd.isna(value) else str(value)


def _matrix(
    scores: List[ClientScoreSchema],
    total_target: float
) -> List[ClusterCellSchema]:
    '''
        The cluster-by-semaphore matrix, with each cell's weight.

        Args:
            scores (List[ClientScoreSchema]): Every scored client-month.
            total_target (float): The whole objective, for the weights.

        Returns:
            List[ClusterCellSchema]: The cells, heaviest first.
    '''
    cells: Dict[Tuple[str, Semaphore], Dict[str, float]] = {}
    for score in scores:
        key = (score.cluster or _NO_CLUSTER, score.invoiced_semaphore)
        cell = cells.setdefault(key, {'clients': 0.0, 'target': 0.0,
                                      'invoiced': 0.0, 'collected': 0.0})
        cell['clients'] += 1
        cell['target'] += score.target_amount
        cell['invoiced'] += score.invoiced_amount
        cell['collected'] += score.collected_amount

    built = [
        ClusterCellSchema(
            cluster = cluster,
            semaphore = semaphore,
            clients_count = int(cell['clients']),
            target_amount = round(cell['target'], _AMOUNTS),
            invoiced_amount = round(cell['invoiced'], _AMOUNTS),
            collected_amount = round(cell['collected'], _AMOUNTS),
            debt_amount = round(cell['invoiced'] - cell['collected'], _AMOUNTS),
            invoiced_ratio = _ratio(cell['invoiced'], cell['target']),
            weight_on_target = _ratio(cell['target'], total_target)
        )
        for (cluster, semaphore), cell in cells.items()
    ]
    return sorted(built, key = lambda cell: cell.weight_on_target, reverse = True)


def build_objectives(
    sales: pd.DataFrame,
    objectives: Optional[pd.DataFrame],
    collections: Optional[pd.DataFrame],
    stored_policy: Optional[Dict]
) -> ObjectivesBlockSchema:
    '''
        Builds the attainment block for a dataset.

        A client with sales and no objective is COUNTED and not scored: a
        percentage against a target nobody set would be an invention, and
        hiding them would let a whole segment fall off the report. A client
        with an objective and no sales scores zero, which is the entire point
        of having loaded the objective.

        Args:
            sales (pd.DataFrame): Normalized sales rows of the dataset.
            objectives (pd.DataFrame | None): Objectives INGEST attached, if
                the account loaded them.
            collections (pd.DataFrame | None): Payments, if loaded. Without
                them nothing is collected and every invoice reads as debt,
                which is what an account that has not loaded payments should
                see.
            stored_policy (Dict | None): The account's policy, if it set one.

        Returns:
            ObjectivesBlockSchema: Totals, matrix and every client behind it.
    '''
    policy = resolve_policy(stored_policy)
    if objectives is None or objectives.empty or _TARGET not in objectives.columns:
        message = 'No objectives attached to the dataset; attainment is empty.'
        logger.info(message)
        return ObjectivesBlockSchema(
            totals = _totals([], []),
            policy = policy,
            clients_without_objective = int(sales[_POS].nunique())
            if _POS in sales.columns else 0
        )

    targets = objectives.loc[:, [_POS, _PERIOD, _TARGET]].copy()
    targets[_POS] = targets[_POS].astype(str)
    targets = targets.groupby([_POS, _PERIOD], as_index = False)[_TARGET].sum()

    invoiced = _invoiced_by_client_period(sales)
    invoiced[_POS] = invoiced[_POS].astype(str)
    collected = _collected_by_client_period(sales, collections)

    merged = targets.merge(invoiced, on = [_POS, _PERIOD], how = 'left')
    merged = merged.merge(collected, on = [_POS, _PERIOD], how = 'left')
    merged = merged.join(_descriptors_of(sales), on = _POS)

    scores = _score_rows(merged, policy)
    totals = _totals(scores, sorted({score.period for score in scores}))
    without = set(invoiced[_POS]) - set(targets[_POS])

    message = (f'Attainment built for {totals.clients_count} client-month(s) over '
               f'{len(totals.periods)} period(s); {len(without)} client(s) with no objective.')
    logger.info(message)

    return ObjectivesBlockSchema(
        totals = totals,
        by_cluster = _matrix(scores, totals.target_amount),
        clients = scores,
        policy = policy,
        clients_without_objective = len(without)
    )


def _totals(
    scores: List[ClientScoreSchema],
    periods: List[str]
) -> ObjectivesTotalsSchema:
    '''
        The header line over every scored client-month.

        Args:
            scores (List[ClientScoreSchema]): The scores.
            periods (List[str]): The months covered.

        Returns:
            ObjectivesTotalsSchema: The totals.
    '''
    target = sum(score.target_amount for score in scores)
    invoiced = sum(score.invoiced_amount for score in scores)
    collected = sum(score.collected_amount for score in scores)
    return ObjectivesTotalsSchema(
        clients_count = len({score.pos_id for score in scores}),
        periods = periods,
        target_amount = round(target, _AMOUNTS),
        invoiced_amount = round(invoiced, _AMOUNTS),
        collected_amount = round(collected, _AMOUNTS),
        debt_amount = round(invoiced - collected, _AMOUNTS),
        invoiced_ratio = _ratio(invoiced, target),
        collected_ratio = _ratio(collected, target),
        debt_ratio = _ratio(invoiced - collected, target),
        points = round(sum(score.points for score in scores), _RATIOS)
    )
