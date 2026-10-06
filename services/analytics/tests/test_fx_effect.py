'''
    Tests for the exchange-rate effect, one per case of
    `docs/cambios/smartdecisions-tipo-cambio-factores/spec.md`.

    The function under test is pure: it receives the sales in bolivianos, the
    rate of each row's own day and today's rate. Reaching QUOTES is the
    controller's job.
'''
import pandas as pd

from schemas.objectives import CommercialPolicySchema
from services.fx_effect import build_fx_effect


def _sale(
    when: str,
    product: str,
    quantity: float,
    price_cost: tuple,
    category: str = 'LACTEOS'
) -> dict:
    '''
        One sales line.

        Args:
            when (str): Day.
            product (str): Product id and name.
            quantity (float): Units.
            price_cost (tuple): Unit price and unit cost, Bs.
            category (str): Category.

        Returns:
            dict: The row.
    '''
    price, cost = price_cost
    return {'date': when, 'product_id': product, 'product_name': product,
            'category': category, 'quantity': quantity, 'unit_price': price,
            'unit_cost': cost, 'total_amount': quantity * price}


def _policy(
    share: float = 1.0,
    by_category: dict | None = None
) -> CommercialPolicySchema:
    '''
        A policy with the given dollar share of the cost.

        Args:
            share (float): Default share.
            by_category (dict | None): Shares by category.

        Returns:
            CommercialPolicySchema: The policy.
    '''
    return CommercialPolicySchema(usd_cost_share = share,
                                  usd_cost_share_by_category = by_category or {})


def _build(
    sales: list,
    rates: list,
    today: float,
    policy: CommercialPolicySchema | None = None
):
    '''
        Runs the effect over rows and their rates.

        Args:
            sales (list): Rows.
            rates (list): Rate of each row's day.
            today (float): Today's rate.
            policy (CommercialPolicySchema | None): Dollar share of the cost.

        Returns:
            FxEffectBlock: The effect.
    '''
    return build_fx_effect(pd.DataFrame(sales), pd.Series(rates, dtype = 'float64'),
                           today, policy or _policy())


def test_a_sale_reads_in_dollars_at_the_rate_of_its_day():
    '''Case 1: Bs 696 on a day at 6.96 is USD 100.'''
    block = _build([_sale('2026-07-10', 'LECHE', 10, (69.6, 50))], [6.96], 6.96)
    assert block.monthly[0].sales_usd == 100.0
    assert block.monthly[0].sales_bob == 696.0


def test_growth_in_bolivianos_can_be_a_fall_in_dollars():
    '''Case 2: sales up 10 % in Bs while the rate rises 15 % fall in USD.'''
    block = _build([_sale('2026-07-10', 'LECHE', 10, (100, 50)),
                    _sale('2026-09-10', 'LECHE', 11, (100, 50))], [7.00, 8.05], 8.05)
    assert block.growth_bob_pct == 10.0
    assert block.growth_usd_pct < 0


def test_the_replacement_cost_is_the_dollar_cost_at_today_s_rate():
    '''Case 3: cost Bs 50 bought at 6.96 costs Bs 57.47 to replace at 8.00.'''
    block = _build([_sale('2026-07-10', 'LECHE', 1, (70, 50))], [6.96], 8.00)
    assert round(block.totals.replacement_cost, 2) == 57.47
    assert block.totals.historical_cost == 50.0


def test_a_price_below_its_replacement_cost_is_flagged():
    '''Case 4: price Bs 55 against a replacement of Bs 57.47.'''
    block = _build([_sale('2026-07-10', 'LECHE', 1, (55, 50)),
                    _sale('2026-07-10', 'QUESO', 1, (90, 50))], [6.96, 6.96], 8.00)
    flagged = {row.product_id: row for row in block.uncovered}
    assert set(flagged) == {'LECHE'}
    assert round(flagged['LECHE'].replacement_cost, 2) == 57.47
    assert round(flagged['LECHE'].gap, 2) == -2.47


def test_a_category_bought_in_bolivianos_keeps_its_historical_cost():
    '''Case 5: with 0 % of the cost in dollars, replacing costs what it cost.'''
    policy = _policy(by_category = {'PAN': 0.0})
    block = _build([_sale('2026-07-10', 'MARRAQUETA', 1, (2, 1.5), category = 'PAN')],
                   [6.96], 8.00, policy)
    assert block.totals.replacement_cost == 1.5
    assert block.by_category[0].usd_cost_share == 0.0


def test_purchasing_power_compares_each_day_with_today():
    '''What was sold buys fewer dollars of merchandise at today's rate.'''
    block = _build([_sale('2026-07-10', 'LECHE', 10, (69.6, 50))], [6.96], 8.00)
    power = block.purchasing_power
    assert power.usd_at_own_day == 100.0
    assert power.usd_at_today == 87.0
    assert power.difference == -13.0
