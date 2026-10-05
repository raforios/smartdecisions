'''
    Tests for objective attainment.

    The first one is the important one: it reproduces three real lines of the
    prospect's own closing workbook, to four decimals. That is the only
    evidence that matters here — the block exists to answer a report they
    already produce by hand, and agreeing with our own arithmetic would prove
    nothing.

    The rest defend the two readings that are easy to get wrong: a payment
    belongs to the month of the INVOICE it settles, and a client nobody gave
    an objective to is counted rather than scored.
'''
from datetime import date

import pandas as pd
import pytest

from schemas.objectives import Semaphore
from services.objectives import build_objectives, resolve_policy, select_objective_periods


# Rates as the prospect sets them. The product declares no cluster names.
POLICY = {'points_per_cluster': {'PLATINIUM': 20.0, 'GOLD': 7.0, 'SILVER': 7.0}}


def _sale(
    pos_id: str,
    cluster: str,
    order_id: str,
    amount: float,
    when: str = '2025-01-15'
) -> dict:
    '''
        One sales line.

        Args:
            pos_id (str): Client identifier.
            cluster (str): Commercial cluster.
            order_id (str): Invoice number.
            amount (float): Line total.
            when (str): Invoice date.

        Returns:
            dict: The row.
    '''
    return {'pos_id': pos_id, 'pos_name': pos_id, 'cluster': cluster,
            'date': when, 'order_id': order_id, 'total_amount': amount}


@pytest.fixture(name = 'closing')
def closing_fixture():
    '''
        Three lines of the prospect's January closing, verbatim.

        Returns:
            tuple: Sales, objectives and collections frames.
    '''
    sales = pd.DataFrame([
        _sale('ABEL', 'SILVER', 'F1', 9385.84),
        _sale('ALIZON', 'SILVER', 'F2', 11197.54),
        _sale('ADELA', 'PLATINIUM', 'F3', 82688.19)
    ])
    objectives = pd.DataFrame([
        {'pos_id': 'ABEL', 'period': '2025-01', 'target_amount': 13940.0},
        {'pos_id': 'ALIZON', 'period': '2025-01', 'target_amount': 18360.0},
        {'pos_id': 'ADELA', 'period': '2025-01', 'target_amount': 82620.0}
    ])
    collections = pd.DataFrame([
        {'order_id': 'F1', 'paid_amount': 9385.84},
        {'order_id': 'F2', 'paid_amount': 6175.99},
        {'order_id': 'F3', 'paid_amount': 82688.19}
    ])
    return sales, objectives, collections


def test_the_block_reproduces_the_prospects_own_closing(closing):
    '''
        Their spreadsheet, to four decimals, including the case that makes the
        block worth building: ALIZON is YELLOW on what they bought and RED on
        what they paid. A report showing only the first would call that
        client acceptable.
    '''
    block = build_objectives(*closing, POLICY)
    scored = {score.pos_id: score for score in block.clients}

    assert scored['ABEL'].invoiced_ratio == 0.6733
    assert scored['ABEL'].invoiced_semaphore is Semaphore.YELLOW
    assert scored['ADELA'].invoiced_ratio == 1.0008
    assert scored['ADELA'].invoiced_semaphore is Semaphore.GREEN

    alizon = scored['ALIZON']
    assert (alizon.invoiced_ratio, alizon.collected_ratio) == (0.6099, 0.3364)
    assert alizon.invoiced_semaphore is Semaphore.YELLOW
    assert alizon.collected_semaphore is Semaphore.RED
    assert alizon.debt_amount == 5021.55


def test_points_are_earned_at_the_clusters_own_rate(closing):
    '''
        A platinum bolivian is worth less in points than a silver one, and
        the rates are the account's: 82688.19 over 20, and 9385.84 over 7.
    '''
    scored = {score.pos_id: score for score in build_objectives(*closing, POLICY).clients}

    assert scored['ADELA'].points == round(82688.19 / 20, 4)
    assert scored['ABEL'].points == round(9385.84 / 7, 4)


def test_the_identity_invoiced_equals_collected_plus_debt_holds(closing):
    '''
        The whole block rests on this. If it ever stops holding, a month's
        debt has been attributed to another month.
    '''
    totals = build_objectives(*closing, POLICY).totals

    assert totals.invoiced_amount == round(totals.collected_amount + totals.debt_amount, 2)
    assert totals.target_amount == 114920.0


def test_a_payment_belongs_to_the_month_of_the_invoice_it_settles():
    '''
        A January invoice paid in March is January's collection, not March's.

        Reading it the other way leaves January permanently in debt and gives
        March a surplus it never earned — and it breaks the identity above.
    '''
    sales = pd.DataFrame([_sale('ABEL', 'SILVER', 'F1', 1000.0, '2025-01-15')])
    objectives = pd.DataFrame([
        {'pos_id': 'ABEL', 'period': '2025-01', 'target_amount': 1000.0}
    ])
    collections = pd.DataFrame([
        {'order_id': 'F1', 'paid_amount': 1000.0, 'payment_date': '2025-03-20'}
    ])

    block = build_objectives(sales, objectives, collections, POLICY)

    assert block.totals.periods == ['2025-01']
    assert block.clients[0].collected_amount == 1000.0
    assert block.clients[0].debt_amount == 0.0


def test_without_payments_everything_invoiced_reads_as_debt():
    '''
        An account that has not loaded collections sees full debt, which is
        the honest answer: nothing says those invoices were paid.
    '''
    sales = pd.DataFrame([_sale('ABEL', 'SILVER', 'F1', 1000.0)])
    objectives = pd.DataFrame([
        {'pos_id': 'ABEL', 'period': '2025-01', 'target_amount': 1000.0}
    ])

    block = build_objectives(sales, objectives, None, POLICY)

    assert block.clients[0].invoiced_semaphore is Semaphore.GREEN
    assert block.clients[0].collected_semaphore is Semaphore.RED
    assert block.totals.debt_ratio == 1.0


def test_a_cash_sale_is_collected_when_it_is_made():
    '''
        A CONTADO invoice was paid at the counter and never appears in the
        collections file. Reading it as debt put Distribuidora Andina's whole
        cash sales (Bs 994.287) into the debt column, against a receivables
        block that rightly did not count them.
    '''
    sales = pd.DataFrame([
        {**_sale('ABEL', 'SILVER', 'F1', 1000.0), 'payment_terms': 'CONTADO'},
        {**_sale('ABEL', 'SILVER', 'F2', 500.0), 'payment_terms': 'CREDITO'}
    ])
    objectives = pd.DataFrame([
        {'pos_id': 'ABEL', 'period': '2025-01', 'target_amount': 1500.0}
    ])
    collections = pd.DataFrame([{'order_id': 'F2', 'paid_amount': 200.0}])

    with_payments = build_objectives(sales, objectives, collections, POLICY).clients[0]
    without_payments = build_objectives(sales, objectives, None, POLICY).clients[0]

    assert (with_payments.collected_amount, with_payments.debt_amount) == (1200.0, 300.0)
    assert (without_payments.collected_amount, without_payments.debt_amount) == (1000.0, 500.0)


def test_a_client_with_no_objective_is_counted_and_never_scored():
    '''
        Scoring them would mean inventing a target; hiding them would let a
        whole segment fall off the report. So they are counted.
    '''
    sales = pd.DataFrame([
        _sale('ABEL', 'SILVER', 'F1', 1000.0),
        _sale('SIN_OBJETIVO', 'SILVER', 'F2', 5000.0)
    ])
    objectives = pd.DataFrame([
        {'pos_id': 'ABEL', 'period': '2025-01', 'target_amount': 1000.0}
    ])

    block = build_objectives(sales, objectives, None, POLICY)

    assert [score.pos_id for score in block.clients] == ['ABEL']
    assert block.clients_without_objective == 1


def test_a_client_with_an_objective_and_no_sales_scores_zero():
    '''
        This is the entire reason for loading objectives: the client who
        bought nothing is invisible in a sales file and unmissable here.
    '''
    sales = pd.DataFrame([_sale('ABEL', 'SILVER', 'F1', 1000.0)])
    objectives = pd.DataFrame([
        {'pos_id': 'ABEL', 'period': '2025-01', 'target_amount': 1000.0},
        {'pos_id': 'DORMIDO', 'period': '2025-01', 'target_amount': 9000.0}
    ])

    scored = {score.pos_id: score for score in
              build_objectives(sales, objectives, None, POLICY).clients}

    assert scored['DORMIDO'].invoiced_amount == 0.0
    assert scored['DORMIDO'].invoiced_ratio == 0.0
    assert scored['DORMIDO'].invoiced_semaphore is Semaphore.RED


def test_the_matrix_weights_each_cell_against_the_whole_objective(closing):
    '''
        Twenty red clients worth two per cent of the objective are a
        different morning from three worth forty, and the weight is what says
        which one it is.
    '''
    block = build_objectives(*closing, POLICY)

    assert sum(cell.clients_count for cell in block.by_cluster) == 3
    assert round(sum(cell.weight_on_target for cell in block.by_cluster), 4) == 1.0
    # Heaviest first: one platinum client carries most of the objective.
    assert block.by_cluster[0].cluster == 'PLATINIUM'


def test_an_account_without_objectives_gets_an_empty_block_not_an_error():
    '''
        Nothing loaded is the ordinary starting state, not a failure — and
        the clients who did invoice are still reported as unscored.
    '''
    sales = pd.DataFrame([_sale('ABEL', 'SILVER', 'F1', 1000.0)])

    block = build_objectives(sales, None, None, None)

    assert block.clients == []
    assert block.totals.target_amount == 0.0
    assert block.clients_without_objective == 1


def test_the_account_policy_overrides_the_defaults_field_by_field():
    '''
        An account that only moves the green cut should not have to restate
        the rest of the yardstick.
    '''
    resolved = resolve_policy({'green_from': 0.9})

    assert resolved.green_from == 0.9
    assert resolved.yellow_from == 0.5
    assert resolved.bs_per_point == 7.0


def test_a_cluster_without_a_rate_falls_back_to_the_default():
    '''
        A cluster the account never priced still earns points, at the
        service default: silently earning zero would look like a bug in the
        sales, not a gap in the configuration.
    '''
    sales = pd.DataFrame([_sale('ABEL', 'BRONCE', 'F1', 700.0)])
    objectives = pd.DataFrame([
        {'pos_id': 'ABEL', 'period': '2025-01', 'target_amount': 700.0}
    ])

    block = build_objectives(sales, objectives, None, POLICY)

    assert block.clients[0].points == 100.0


def test_without_a_window_only_the_latest_month_is_judged():
    '''
        Twenty-four months of objectives were 2,4 MB on the wire. With no
        window the block judges the closing month only, and says which months
        there are so the screen can offer the rest.
    '''
    objectives = pd.DataFrame([
        {'pos_id': 'ABEL', 'period': period, 'target_amount': 1000.0}
        for period in ('2025-01', '2025-02', '2025-03')
    ])

    chosen, available = select_objective_periods(objectives, None, None)

    assert sorted(chosen['period'].unique()) == ['2025-03']
    assert available == ['2025-01', '2025-02', '2025-03']


def test_a_window_judges_the_months_it_covers():
    '''The window the user picks decides the months, partial months included.'''
    objectives = pd.DataFrame([
        {'pos_id': 'ABEL', 'period': period, 'target_amount': 1000.0}
        for period in ('2025-01', '2025-02', '2025-03')
    ])

    chosen, _ = select_objective_periods(objectives, date(2025, 1, 15), date(2025, 2, 10))

    assert sorted(chosen['period'].unique()) == ['2025-01', '2025-02']
