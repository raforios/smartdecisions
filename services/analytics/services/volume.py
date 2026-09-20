'''
    Volume-source engine — where the volume comes from.

    Answers the question a ranking only half answers: not just which products
    sell most, but what share of the whole each one carries, how many clients
    reach for it, which product anchors each client, and where the movement of
    the last month actually came from.

    It was assembled from pieces that lived in three other blocks — the
    category mix inside growth, the ABC inside concentration, a top-products
    ranking inside the summary — none of which crossed client with product.
    Those pieces moved here instead of being copied: the same number in two
    places is two numbers the day one of them changes.

    Columns used (all produced by ingest normalization; each section is skipped
    when its column is missing):
        total_amount, quantity, pos_id, pos_name, product_id, product_name,
        category, date
'''
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from schemas.analytics import (
    AbcClass,
    CategoryMix,
    VolumeClient,
    VolumeDecomposition,
    VolumeEffect,
    VolumeHeadline,
    VolumeMatrixCell,
    VolumeProduct,
    VolumeSourceBlock
)
from services.analytics_utils import (
    AMOUNT,
    CATEGORY,
    CLIENT_ID,
    CLIENT_NAME,
    CHANGE_DECIMALS,
    PRODUCT_ID,
    PRODUCT_NAME,
    QUANTITY,
    dates,
    hhi_level,
    label_series,
    money,
    percent_change,
    ratio
)
from services.environment import load_and_validate_env_vars
from services.logger_config import custom_logger as logger

# Business thresholds: configurable per deployment, never literals in the code.
# They repeat the concentration ones on purpose — the same cut points applied
# to products instead of clients — so a distributor can move one without
# moving the other.
_SETTINGS = load_and_validate_env_vars({
    'VOLUME_PARETO_TARGET': float,
    'VOLUME_ABC_A_LIMIT': float,
    'VOLUME_ABC_B_LIMIT': float,
    'VOLUME_TOP_PRODUCTS': int,
    'VOLUME_TOP_CLIENTS': int,
    'VOLUME_MATRIX_CLIENTS': int,
    'VOLUME_MATRIX_PRODUCTS': int,
    'VOLUME_HHI_MODERATE': float,
    'VOLUME_HHI_HIGH': float,
})
_PARETO_TARGET = _SETTINGS['VOLUME_PARETO_TARGET']
_ABC_A_LIMIT = _SETTINGS['VOLUME_ABC_A_LIMIT']
_ABC_B_LIMIT = _SETTINGS['VOLUME_ABC_B_LIMIT']
_TOP_PRODUCTS = _SETTINGS['VOLUME_TOP_PRODUCTS']
_TOP_CLIENTS = _SETTINGS['VOLUME_TOP_CLIENTS']
_MATRIX_CLIENTS = _SETTINGS['VOLUME_MATRIX_CLIENTS']
_MATRIX_PRODUCTS = _SETTINGS['VOLUME_MATRIX_PRODUCTS']
_HHI_MODERATE = _SETTINGS['VOLUME_HHI_MODERATE']
_HHI_HIGH = _SETTINGS['VOLUME_HHI_HIGH']

# Two decimals on shares, not the `CHANGE_DECIMALS` used for variations: a
# long-tail SKU weighs 0.35% of the volume and rounded to one decimal it reads
# as 0.4% or disappears. The Pareto curve needs the second decimal for the
# cumulative column to keep closing at 100.
_SHARE_DECIMALS = 2

# Codes of the decomposition terms. They travel as codes because the sentence
# that explains "the joint term" to a manager belongs to the frontend.
_PRICE = 'PRICE'
_QUANTITY_EFFECT = 'QUANTITY'
_JOINT = 'JOINT'
_ENTRY = 'ENTRY'
_EXIT = 'EXIT'
_NEW_CLIENTS = 'NEW_CLIENTS'
_LOST_CLIENTS = 'LOST_CLIENTS'
_RETAINED_CLIENTS = 'RETAINED_CLIENTS'


def _labelled(dataframe: pd.DataFrame) -> Optional[pd.DataFrame]:
    '''
        Adds readable client and product labels to the frame.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows.

        Returns:
            pd.DataFrame | None: The frame with `_client` and `_product`, or
                None when it cannot support the block at all.
    '''
    if AMOUNT not in dataframe.columns:
        return None

    clients = label_series(dataframe, CLIENT_ID, CLIENT_NAME)
    products = label_series(dataframe, PRODUCT_ID, PRODUCT_NAME)
    if products is None:
        return None

    frame = dataframe.assign(_product = products.values)
    frame['_client'] = clients.values if clients is not None else ''
    if QUANTITY not in frame.columns:
        frame[QUANTITY] = 0.0
    return frame.loc[frame[AMOUNT] > 0]


def _abc_class(preceding: float) -> str:
    '''
        Returns the ABC class of a product from the share that PRECEDES it.

        The share accumulated before the product, not the one that includes it:
        a product concentrating 99% of the sales has a cumulative share of 0,99
        and came out class C, when by definition it is the first A of the
        catalogue. The item that crosses a threshold belongs to the class that
        crosses it.

        Args:
            preceding (float): Cumulative share of everything sold more than
                this product, 0 to 1.

        Returns:
            str: 'A', 'B' or 'C'.
    '''
    if preceding < _ABC_A_LIMIT:
        return 'A'
    if preceding < _ABC_B_LIMIT:
        return 'B'
    return 'C'


def _pareto_point(cumulative: pd.Series) -> int:
    '''
        How many items are needed to reach the Pareto target.

        Args:
            cumulative (pd.Series): Cumulative share, ascending, 0 to 1.

        Returns:
            int: Count of items, never more than the items available.
    '''
    if cumulative.empty:
        return 0
    return min(int((cumulative < _PARETO_TARGET).sum()) + 1, len(cumulative))


def _product_rows(
    frame: pd.DataFrame
) -> Tuple[List[VolumeProduct], VolumeHeadline, List[AbcClass]]:
    '''
        The Pareto of products with its headline figures and ABC summary.

        Args:
            frame (pd.DataFrame): Labelled sales rows.

        Returns:
            tuple: (product rows, headline, ABC summary). The rows are capped
                at the configured top; the headline and the summary are
                computed over the **whole** catalogue, so a cap never changes
                a percentage.
    '''
    grouped = frame.groupby('_product').agg(
        amount = (AMOUNT, 'sum'),
        units = (QUANTITY, 'sum'),
        clients = ('_client', 'nunique')
    ).sort_values('amount', ascending = False)

    total = float(grouped['amount'].sum())
    if total <= 0:
        return [], VolumeHeadline(), []

    shares = grouped['amount'] / total
    cumulative = shares.cumsum()
    classes = [_abc_class(value) for value in (cumulative - shares)]
    grouped = grouped.assign(
        share = shares.values, cumulative = cumulative.values, abc_class = classes
    )

    summary = []
    for abc_class in ('A', 'B', 'C'):
        rows = grouped.loc[grouped['abc_class'] == abc_class]
        class_amount = float(rows['amount'].sum())
        summary.append(AbcClass(
            abc_class = abc_class,
            products = int(len(rows)),
            amount = money(class_amount),
            percentage = round(ratio(class_amount, total) * 100, 1)
        ))

    top = grouped.head(_TOP_PRODUCTS)
    products = [
        VolumeProduct(
            label = str(label),
            amount = money(row['amount']),
            units = money(row['units']),
            share = round(float(row['share']) * 100, _SHARE_DECIMALS),
            cumulative = round(float(row['cumulative']) * 100, _SHARE_DECIMALS),
            abc_class = str(row['abc_class']),
            clients = int(row['clients'])
        )
        for label, row in top.iterrows()
    ]

    hhi = float((shares ** 2).sum())
    top_amount = float(top['amount'].sum())
    headline = VolumeHeadline(
        total_products = int(len(grouped)),
        pareto_products = _pareto_point(cumulative),
        pareto_product_percentage = round(
            ratio(_pareto_point(cumulative), len(grouped)) * 100, 1
        ),
        top_products_amount = money(top_amount),
        top_products_percentage = round(ratio(top_amount, total) * 100, 1),
        top_products_count = int(len(top)),
        hhi = round(hhi, 4),
        hhi_level = hhi_level(hhi, _HHI_MODERATE, _HHI_HIGH).value
    )
    return products, headline, summary


def _client_rows(frame: pd.DataFrame) -> List[VolumeClient]:
    '''
        The Pareto of clients, each with the product that anchors it.

        Args:
            frame (pd.DataFrame): Labelled sales rows.

        Returns:
            List[VolumeClient]: Rows for the configured top of clients.
    '''
    if not frame['_client'].astype(str).str.strip().any():
        return []

    grouped = frame.groupby('_client').agg(
        amount = (AMOUNT, 'sum'),
        products = ('_product', 'nunique')
    ).sort_values('amount', ascending = False)

    total = float(grouped['amount'].sum())
    if total <= 0:
        return []

    cumulative = (grouped['amount'] / total).cumsum()
    top = grouped.head(_TOP_CLIENTS)

    # The anchor is read per client and only for the rows shown: the full
    # cross-tab of a real catalogue is hundreds of thousands of cells.
    anchors = (
        frame.loc[frame['_client'].isin(top.index)]
        .groupby(['_client', '_product'])[AMOUNT].sum()
    )

    rows = []
    for label, row in top.iterrows():
        client_products = anchors.loc[label].sort_values(ascending = False)
        anchor_label = str(client_products.index[0])
        anchor_amount = float(client_products.iloc[0])
        rows.append(VolumeClient(
            label = str(label),
            amount = money(row['amount']),
            share = round(ratio(row['amount'], total) * 100, _SHARE_DECIMALS),
            cumulative = round(float(cumulative.loc[label]) * 100, _SHARE_DECIMALS),
            products = int(row['products']),
            anchor_product = anchor_label,
            anchor_share = round(ratio(anchor_amount, row['amount']) * 100, 1)
        ))
    return rows


def _matrix_rows(frame: pd.DataFrame) -> List[VolumeMatrixCell]:
    '''
        The client × product intersections that carry the volume.

        Only the top clients against the top products: the full cross-tab is
        unreadable and most of it is zeros. Each cell is read from both sides,
        because the same amount can be trivial for the client and vital for the
        product.

        Args:
            frame (pd.DataFrame): Labelled sales rows.

        Returns:
            List[VolumeMatrixCell]: Non-empty intersections, largest first.
    '''
    if not frame['_client'].astype(str).str.strip().any():
        return []

    client_totals = frame.groupby('_client')[AMOUNT].sum().sort_values(ascending = False)
    product_totals = frame.groupby('_product')[AMOUNT].sum().sort_values(ascending = False)
    clients = client_totals.head(_MATRIX_CLIENTS).index
    products = product_totals.head(_MATRIX_PRODUCTS).index

    scoped = frame.loc[frame['_client'].isin(clients) & frame['_product'].isin(products)]
    if scoped.empty:
        return []

    cells = scoped.groupby(['_client', '_product']).agg(
        amount = (AMOUNT, 'sum'), units = (QUANTITY, 'sum')
    ).sort_values('amount', ascending = False)

    return [
        VolumeMatrixCell(
            client = str(client),
            product = str(product),
            amount = money(row['amount']),
            units = money(row['units']),
            client_share = round(
                ratio(row['amount'], float(client_totals.loc[client])) * 100, 1
            ),
            product_share = round(
                ratio(row['amount'], float(product_totals.loc[product])) * 100, 1
            )
        )
        for (client, product), row in cells.iterrows()
    ]


def _category_mix(
    frame: pd.DataFrame,
    parsed_dates: pd.Series,
    months: Tuple[str, str]
) -> List[CategoryMix]:
    '''
        Category shares of the last month against the previous one, so a shift
        inside a flat total becomes visible.

        Moved here from the growth block: a category gaining weight is a
        statement about where the volume comes from, not about how fast the
        total grows.

        Args:
            frame (pd.DataFrame): Labelled sales rows.
            parsed_dates (pd.Series): Coerced datetimes aligned to the frame.
            months (tuple): (current month key, previous month key).

        Returns:
            List[CategoryMix]: One row per category, biggest gain first.
    '''
    if CATEGORY not in frame.columns:
        return []

    current_key, previous_key = months
    labelled = frame.assign(
        _month = parsed_dates.dt.strftime('%Y-%m'),
        _cat = frame[CATEGORY].fillna('').astype(str)
    )
    current = labelled.loc[labelled['_month'] == current_key].groupby('_cat')[AMOUNT].sum()
    previous = labelled.loc[labelled['_month'] == previous_key].groupby('_cat')[AMOUNT].sum()
    current_total, previous_total = float(current.sum()), float(previous.sum())

    rows = [
        _mix_row(str(category), (current, previous), (current_total, previous_total))
        for category in sorted(set(current.index) | set(previous.index))
    ]
    return sorted(rows, key = lambda row: row.share_change, reverse = True)


def _mix_row(
    category: str,
    amounts: Tuple[pd.Series, pd.Series],
    totals: Tuple[float, float]
) -> CategoryMix:
    '''
        Builds one category row of the mix comparison.

        Args:
            category (str): Category being described.
            amounts (tuple): (current month series, previous month series).
            totals (tuple): (current month total, previous month total).

        Returns:
            CategoryMix: The row, with the share shift in percentage points.
    '''
    current, previous = amounts
    current_total, previous_total = totals
    current_amount = float(current.get(category, 0.0))
    previous_amount = float(previous.get(category, 0.0))
    current_share = round(ratio(current_amount, current_total) * 100, 1)
    previous_share = round(ratio(previous_amount, previous_total) * 100, 1)

    return CategoryMix(
        label = category,
        current_amount = money(current_amount),
        previous_amount = money(previous_amount),
        change = percent_change(current_amount, previous_amount),
        current_share = current_share,
        previous_share = previous_share,
        share_change = round(current_share - previous_share, 1)
    )


def _effects(
    terms: List[Tuple[str, float]],
    change: float
) -> List[VolumeEffect]:
    '''
        Turns raw decomposition terms into rows with their weight.

        Args:
            terms (list): (code, amount) pairs.
            change (float): The move being explained.

        Returns:
            List[VolumeEffect]: The terms that are not zero, largest absolute
                first. The percentage is against the absolute change, so a term
                that pushes against the move reads negative.
    '''
    rows = [
        VolumeEffect(
            effect_code = code,
            amount = money(amount),
            percentage = (
                round(amount / abs(change) * 100, CHANGE_DECIMALS)
                if change else None
            )
        )
        for code, amount in terms
        if round(amount, 2) != 0.0
    ]
    return sorted(rows, key = lambda row: abs(row.amount), reverse = True)


def _product_effects(
    current: pd.DataFrame,
    previous: pd.DataFrame
) -> List[Tuple[str, float]]:
    '''
        Splits the move into price, quantity, their joint term and the products
        that entered or left.

        For a product in both months the identity is exact:
        p1q1 - p0q0 = p0(q1-q0) + q0(p1-p0) + (p1-p0)(q1-q0). The price used is
        the realized one (amount ÷ units), which is what was actually charged
        after discounts, not what a price list says.

        Args:
            current (pd.DataFrame): Amount and units per product, last month.
            previous (pd.DataFrame): The same, month before.

        Returns:
            List[Tuple[str, float]]: (code, amount) terms.
    '''
    common = current.index.intersection(previous.index)
    price = quantity = joint = 0.0

    for label in common:
        current_units = float(current.loc[label, 'units'])
        previous_units = float(previous.loc[label, 'units'])
        current_amount = float(current.loc[label, 'amount'])
        previous_amount = float(previous.loc[label, 'amount'])
        if current_units <= 0 or previous_units <= 0:
            # Without units on both sides there is no price to separate; the
            # whole move of that product is quantity.
            quantity += current_amount - previous_amount
            continue
        current_price = current_amount / current_units
        previous_price = previous_amount / previous_units
        quantity += previous_price * (current_units - previous_units)
        price += previous_units * (current_price - previous_price)
        joint += (current_price - previous_price) * (current_units - previous_units)

    entry = float(current.loc[current.index.difference(previous.index), 'amount'].sum())
    exit_amount = -float(previous.loc[previous.index.difference(current.index), 'amount'].sum())

    return [(_PRICE, price), (_QUANTITY_EFFECT, quantity), (_JOINT, joint),
            (_ENTRY, entry), (_EXIT, exit_amount)]


def _client_effects(
    current: pd.Series,
    previous: pd.Series
) -> List[Tuple[str, float]]:
    '''
        Splits the same move into new, lost and retained clients.

        Args:
            current (pd.Series): Amount per client, last month.
            previous (pd.Series): Amount per client, month before.

        Returns:
            List[Tuple[str, float]]: (code, amount) terms.
    '''
    common = current.index.intersection(previous.index)
    retained = float(current.loc[common].sum() - previous.loc[common].sum())
    new_clients = float(current.loc[current.index.difference(previous.index)].sum())
    lost_clients = -float(previous.loc[previous.index.difference(current.index)].sum())

    return [(_NEW_CLIENTS, new_clients), (_LOST_CLIENTS, lost_clients),
            (_RETAINED_CLIENTS, retained)]


def _monthly_keys(
    frame: pd.DataFrame,
    parsed_dates: pd.Series
) -> Optional[Tuple[str, str]]:
    '''
        The last two months with sales, or None when there is only one.

        Args:
            frame (pd.DataFrame): Labelled sales rows.
            parsed_dates (pd.Series): Coerced datetimes aligned to the frame.

        Returns:
            Tuple[str, str] | None: (current, previous) as 'YYYY-MM'.
    '''
    monthly = (
        frame.assign(_month = parsed_dates.dt.strftime('%Y-%m'))
        .groupby('_month')[AMOUNT].sum().sort_index()
    )
    monthly = monthly[monthly > 0]
    if len(monthly) < 2:
        return None
    months = list(monthly.index)
    return str(months[-1]), str(months[-2])


def _decomposition(
    frame: pd.DataFrame,
    parsed_dates: pd.Series,
    months: Tuple[str, str]
) -> VolumeDecomposition:
    '''
        Where the change between the last two months came from, split two ways.

        Args:
            frame (pd.DataFrame): Labelled sales rows.
            parsed_dates (pd.Series): Coerced datetimes aligned to the frame.
            months (tuple): (current month key, previous month key).

        Returns:
            VolumeDecomposition: Both decompositions of the same delta.
    '''
    current_key, previous_key = months
    labelled = frame.assign(_month = parsed_dates.dt.strftime('%Y-%m'))
    current_rows = labelled.loc[labelled['_month'] == current_key]
    previous_rows = labelled.loc[labelled['_month'] == previous_key]

    def _by_product(rows: pd.DataFrame) -> pd.DataFrame:
        return rows.groupby('_product').agg(amount = (AMOUNT, 'sum'),
                                            units = (QUANTITY, 'sum'))

    current_products = _by_product(current_rows)
    previous_products = _by_product(previous_rows)
    current_amount = float(current_products['amount'].sum())
    previous_amount = float(previous_products['amount'].sum())
    change = current_amount - previous_amount

    by_client: List[VolumeEffect] = []
    if current_rows['_client'].astype(str).str.strip().any():
        by_client = _effects(
            _client_effects(
                current_rows.groupby('_client')[AMOUNT].sum(),
                previous_rows.groupby('_client')[AMOUNT].sum()
            ),
            change
        )

    return VolumeDecomposition(
        current_month = current_key,
        previous_month = previous_key,
        current_amount = money(current_amount),
        previous_amount = money(previous_amount),
        change = money(change),
        change_percentage = percent_change(current_amount, previous_amount),
        by_product = _effects(_product_effects(current_products, previous_products), change),
        by_client = by_client
    )


def build_volume_source(dataframe: pd.DataFrame) -> VolumeSourceBlock:
    '''
        Builds the volume-source block of the commercial summary.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows as produced by the
                ingest service.

        Returns:
            VolumeSourceBlock: Pareto of products and clients, the client ×
                product matrix, the category mix and the decomposition of the
                last move. Sections the data cannot support come back empty
                rather than raising.
    '''
    frame = _labelled(dataframe)
    if frame is None or frame.empty:
        message = ('Volume-source block skipped: the dataset has no usable '
                   'amount or product column.')
        logger.info(message)
        return VolumeSourceBlock()

    products, headline, abc_summary = _product_rows(frame)
    message = (f'Building volume-source block ({headline.total_products} products, '
               f'{frame["_client"].nunique()} clients).')
    logger.info(message)

    block: Dict[str, Any] = {
        'headline': headline,
        'abc_summary': abc_summary,
        'products': products,
        'clients': _client_rows(frame),
        'matrix': _matrix_rows(frame),
    }

    parsed_dates = dates(frame)
    months = _monthly_keys(frame, parsed_dates) if parsed_dates is not None else None
    if months is not None:
        block['category_mix'] = _category_mix(frame, parsed_dates, months)
        block['decomposition'] = _decomposition(frame, parsed_dates, months)

    return VolumeSourceBlock(**block)
