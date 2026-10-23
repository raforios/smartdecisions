'''
    Tests for the objectives contract — the only figure in the product that no
    transaction implies, and therefore the only one that can be wrong without
    any file contradicting it.

    What they defend: a month is read as a month or refused, never guessed; a
    reload corrects a month instead of doubling it; and a client with an
    objective and no invoice is reported rather than dropped, because that is
    the client the company is trying to activate.
'''
from io import BytesIO

import pandas as pd

from schemas.ingest import ValidationRule
from services.objectives import parse_and_validate, prepare_rows, validate_rows


SALES = pd.DataFrame({
    'pos_id': ['ABEL ARUQUIPA LUNA', 'ADELA TICONA MAMANI'],
    'total_amount': [28300.0, 165716.14]
})


def _book(rows: list) -> bytes:
    '''
        An objectives workbook with the published Spanish headers.

        Args:
            rows (list): Dicts keyed by template header.

        Returns:
            bytes: The workbook.
    '''
    buffer = BytesIO()
    pd.DataFrame(rows).to_excel(buffer, index = False)
    return buffer.getvalue()


def _row(
    client: str,
    period: object,
    target: float
) -> dict:
    '''
        One template row.

        Args:
            client (str): Client name.
            period (object): Period cell, as the client wrote it.
            target (float): The objective.

        Returns:
            dict: The row.
    '''
    return {'Cliente': client, 'Periodo': period, 'Objetivo': target}


def test_a_valid_objectives_file_is_accepted_whole():
    '''Two clients, one month: both rows in, nothing reported.'''
    result = parse_and_validate(_book([
        _row('ABEL ARUQUIPA LUNA', '2025-01', 13940.0),
        _row('ADELA TICONA MAMANI', '2025-01', 82620.0)
    ]), 'objetivos.xlsx', SALES)

    assert not result.issues
    assert result.summary.valid_rows == 2
    assert result.summary.target_amount == 96560.0
    assert (result.summary.period_start, result.summary.period_end) == ('2025-01', '2025-01')


def test_a_period_that_is_not_a_month_is_refused_not_guessed():
    '''
        '03/2025' is refused with a code instead of being read as March.

        Guessing is the expensive error here: a quarter silently landing in
        the wrong column produces percentages nobody can audit, while a
        rejected row is visible the moment it happens.
    '''
    result = parse_and_validate(_book([
        _row('ABEL ARUQUIPA LUNA', '2025-01', 13940.0),
        _row('ABEL ARUQUIPA LUNA', '03/2025', 14350.0)
    ]), 'objetivos.xlsx', SALES)

    refused = [issue for issue in result.issues if issue.column == 'period']
    assert len(refused) == 1
    assert refused[0].rule_code is ValidationRule.INVALID_VALUE
    assert len(result.accepted) == 1
    # The client sent two rows and the summary has to say so.
    assert (result.summary.total_rows, result.summary.error_rows) == (2, 1)


def test_a_month_excel_turned_into_a_date_is_still_that_month():
    '''
        Excel converts a cell that looks like a date into a real one, so a
        client who typed 2025-01 can reach us as a Timestamp. Reading it back
        as its own month is not guessing, and refusing it would punish the
        client for their spreadsheet's behaviour.
    '''
    result = parse_and_validate(_book([
        _row('ABEL ARUQUIPA LUNA', pd.Timestamp('2025-03-01'), 14350.0)
    ]), 'objetivos.xlsx', SALES)

    assert not result.issues
    assert result.accepted['period'].iloc[0] == '2025-03'


def test_an_objective_for_a_client_never_invoiced_is_reported_and_kept():
    '''
        The row stays: a client with an objective and no sales is the client
        the company is trying to activate, and dropping it would hide exactly
        the gap a manager is looking for.
    '''
    result = parse_and_validate(_book([
        _row('CLIENTE NUEVO SRL', '2025-01', 5000.0)
    ]), 'objetivos.xlsx', SALES)

    assert [issue.rule_code for issue in result.issues] == [ValidationRule.UNKNOWN_CLIENT]
    assert len(result.accepted) == 1
    assert result.summary.unmatched_rows == 1


def test_a_negative_objective_is_rejected():
    '''An objective below zero is not a decision, it is a typo.'''
    result = parse_and_validate(_book([
        _row('ABEL ARUQUIPA LUNA', '2025-01', -100.0)
    ]), 'objetivos.xlsx', SALES)

    assert [issue.column for issue in result.issues] == ['target_amount']
    assert result.summary.valid_rows == 0


def test_an_empty_file_is_not_an_error():
    '''Nothing loaded, nothing reported: the same as every other contract.'''
    result = parse_and_validate(_book([]), 'objetivos.xlsx', SALES)

    assert not result.issues
    assert result.summary.valid_rows == 0


def test_the_api_channel_is_judged_by_the_same_contract():
    '''
        An ERP pushing canonical rows reaches the same validator with the same
        codes. The two doors are the product's promise; a second validator
        behind one of them would make that promise false.
    '''
    pushed = prepare_rows(pd.DataFrame([
        {'pos_name': 'ABEL ARUQUIPA LUNA', 'period': '2025-01', 'target_amount': 13940.0},
        {'pos_name': 'ABEL ARUQUIPA LUNA', 'period': '03/2025', 'target_amount': 14350.0}
    ]))
    result = validate_rows(pushed, SALES, 'api')

    assert [issue.rule_code for issue in result.issues] == [ValidationRule.INVALID_VALUE]
    assert len(result.accepted) == 1
