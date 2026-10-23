'''
    Unit tests for the volume-source engine.

    Covers what the block is for: the Pareto of products with its reach, the
    client anchored to a single SKU, the client × product matrix read from both
    sides, the category mix that moved here from growth, and the two
    decompositions of the same monthly move.
'''
import pandas as pd

from schemas.analytics import ConcentrationLevel, VolumeSourceBlock
from services.volume import build_volume_source


_CATEGORY = 'Galletas'


def _row(
    client: str,
    product: str,
    amount: float,
    units: float = 1.0,
    date: str = '2026-03-10'
) -> dict:
    '''
        One sales line. The category test overrides `category` on the result,
        so the helper stays inside the five-argument limit.

        Args:
            client (str): Client name.
            product (str): Product name.
            amount (float): Line amount.
            units (float): Units sold.
            date (str): Sale date.

        Returns:
            dict: A normalized sales row.
    '''
    return {
        'order_id': f'F-{client}-{product}-{date}', 'pos_id': client,
        'pos_name': client, 'product_id': product, 'product_name': product,
        'category': _CATEGORY, 'quantity': units, 'total_amount': amount,
        'date': date
    }


def test_products_carry_share_cumulative_and_reach():
    '''
        The Pareto of products: share and cumulative share, plus how many
        clients actually buy each one — two products with the same amount and
        different reach are not the same business.
    '''
    frame = pd.DataFrame([
        _row('C1', 'Estrella', 600.0),
        _row('C2', 'Estrella', 200.0),
        _row('C3', 'Estrella', 200.0),
        _row('C1', 'Nicho', 1000.0),
    ])
    block = build_volume_source(frame)
    products = {row.label: row for row in block.products}

    assert products['Nicho'].share == 50.0
    assert products['Nicho'].clients == 1
    assert products['Estrella'].share == 50.0
    assert products['Estrella'].clients == 3
    # Cumulative is monotonic and closes at 100%.
    assert block.products[-1].cumulative == 100.0


def test_headline_measures_the_whole_catalogue_not_the_shown_rows():
    '''
        The cap on rows must never change a percentage: the Pareto point and
        the HHI are computed over every product, not over the ones displayed.
    '''
    frame = pd.DataFrame(
        [_row('C1', 'Ancla', 8000.0)]
        + [_row('C1', f'Cola{index}', 10.0) for index in range(200)]
    )
    block = build_volume_source(frame)

    assert block.headline.total_products == 201
    assert block.headline.pareto_products == 1
    assert block.headline.hhi_level == ConcentrationLevel.HIGH.value
    assert len(block.products) < block.headline.total_products


def test_anchor_product_exposes_a_single_sku_client():
    '''
        A client buying 95% of one product is a relationship with a SKU, not
        with the company. The anchor share says so.
    '''
    frame = pd.DataFrame([
        _row('Mayorista', 'Leche', 950.0),
        _row('Mayorista', 'Galleta', 50.0),
        _row('Tienda', 'Leche', 500.0),
        _row('Tienda', 'Galleta', 500.0),
    ])
    clients = {row.label: row for row in build_volume_source(frame).clients}

    assert clients['Mayorista'].anchor_product == 'Leche'
    assert clients['Mayorista'].anchor_share == 95.0
    assert clients['Mayorista'].products == 2
    assert clients['Tienda'].anchor_share == 50.0


def test_matrix_reads_each_cell_from_both_sides():
    '''
        The same amount can be marginal for the client and vital for the
        product; the cell carries both weights.
    '''
    frame = pd.DataFrame([
        _row('Grande', 'Exclusivo', 100.0),
        _row('Grande', 'Masivo', 900.0),
        _row('Chico', 'Masivo', 100.0),
    ])
    cells = {
        (cell.client, cell.product): cell
        for cell in build_volume_source(frame).matrix
    }

    exclusive = cells[('Grande', 'Exclusivo')]
    assert exclusive.client_share == 10.0     # apenas 10% de ese cliente
    assert exclusive.product_share == 100.0   # pero todo el producto


def test_category_mix_reports_the_share_shift_in_points():
    '''
        Moved here from growth: a category gaining weight inside a flat total
        is where the volume came from.
    '''
    frame = pd.DataFrame([
        {**_row('C1', 'A', 500.0, date = '2026-01-15'), 'category': 'Lácteos'},
        {**_row('C1', 'B', 500.0, date = '2026-01-15'), 'category': 'Galletas'},
        {**_row('C1', 'A', 800.0, date = '2026-02-15'), 'category': 'Lácteos'},
        {**_row('C1', 'B', 200.0, date = '2026-02-15'), 'category': 'Galletas'},
    ])
    mix = {row.label: row for row in build_volume_source(frame).category_mix}

    assert mix['Lácteos'].previous_share == 50.0
    assert mix['Lácteos'].current_share == 80.0
    assert mix['Lácteos'].share_change == 30.0
    assert mix['Galletas'].share_change == -30.0


def test_price_and_quantity_effects_separate_a_flat_looking_rise():
    '''
        Same units at a higher price is a price effect; same price with more
        units is a quantity effect. Both cases move the total the same way and
        mean opposite things.
    '''
    priced = pd.DataFrame([
        _row('C1', 'A', 100.0, units = 10.0, date = '2026-01-15'),
        _row('C1', 'A', 120.0, units = 10.0, date = '2026-02-15'),
    ])
    effects = {
        row.effect_code: row.amount
        for row in build_volume_source(priced).decomposition.by_product
    }
    assert effects['PRICE'] == 20.0
    assert 'QUANTITY' not in effects

    volumed = pd.DataFrame([
        _row('C1', 'A', 100.0, units = 10.0, date = '2026-01-15'),
        _row('C1', 'A', 120.0, units = 12.0, date = '2026-02-15'),
    ])
    effects = {
        row.effect_code: row.amount
        for row in build_volume_source(volumed).decomposition.by_product
    }
    assert effects['QUANTITY'] == 20.0
    assert 'PRICE' not in effects


def test_both_decompositions_add_up_to_the_same_change():
    '''
        Neither reading may explain more than what happened: the product terms
        and the client terms must each sum to the change.
    '''
    frame = pd.DataFrame([
        _row('Viejo', 'A', 300.0, units = 3.0, date = '2026-01-15'),
        _row('Constante', 'A', 200.0, units = 2.0, date = '2026-01-15'),
        _row('Constante', 'B', 100.0, units = 5.0, date = '2026-01-15'),
        _row('Constante', 'A', 260.0, units = 2.0, date = '2026-02-15'),
        _row('Constante', 'C', 90.0, units = 3.0, date = '2026-02-15'),
        _row('Nuevo', 'B', 400.0, units = 20.0, date = '2026-02-15'),
    ])
    decomposition = build_volume_source(frame).decomposition

    # 600 the previous month (300 + 200 + 100) against 750 the last one
    # (260 + 90 + 400).
    assert decomposition.change == 150.0
    assert round(sum(row.amount for row in decomposition.by_product), 2) == 150.0
    assert round(sum(row.amount for row in decomposition.by_client), 2) == 150.0


def test_client_effects_name_who_moved_the_total():
    '''A new account and a lost one both weigh, with opposite signs.'''
    frame = pd.DataFrame([
        _row('Perdido', 'A', 500.0, date = '2026-01-15'),
        _row('Nuevo', 'A', 800.0, date = '2026-02-15'),
    ])
    effects = {
        row.effect_code: row.amount
        for row in build_volume_source(frame).decomposition.by_client
    }
    assert effects['NEW_CLIENTS'] == 800.0
    assert effects['LOST_CLIENTS'] == -500.0


def test_single_month_leaves_the_decomposition_empty():
    '''
        With one month there is nothing to compare, so the section stays empty
        instead of inventing a baseline of zero.
    '''
    frame = pd.DataFrame([_row('C1', 'A', 100.0)])
    block = build_volume_source(frame)

    assert block.decomposition.change == 0.0
    assert not block.decomposition.by_product
    assert not block.category_mix
    assert block.products


def test_block_is_empty_without_product_or_amount():
    '''A frame the engine cannot read comes back empty, never as an error.'''
    assert build_volume_source(pd.DataFrame({'total_amount': [10.0]})) == VolumeSourceBlock()
    assert build_volume_source(pd.DataFrame({'product_name': ['A']})) == VolumeSourceBlock()
