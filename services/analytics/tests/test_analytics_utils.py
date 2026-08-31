'''
    Unit tests for the shared date-range filter.
'''
import pandas as pd
import pytest

from schemas.analytics import AnalyticsError
from services.analytics_utils import apply_date_range
from services.exceptions import InvalidInputError


def _frame() -> pd.DataFrame:
    '''One row on the first of each month of 2024.'''
    return pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods = 12, freq = 'MS'),
        'total_amount': [100.0] * 12,
    })


def test_no_boundaries_returns_everything_and_reports_the_full_span():
    '''An unfiltered call still describes the period the data covers.'''
    scoped, period = apply_date_range(_frame(), None, None)
    assert len(scoped) == 12
    assert period.filtered is False
    assert period.available_from == '2024-01-01'
    assert period.from_date == period.available_from


def test_boundaries_are_inclusive():
    '''A window must keep the rows landing exactly on its edges.'''
    scoped, period = apply_date_range(_frame(), '2024-03-01', '2024-05-01')
    assert len(scoped) == 3
    assert period.rows == 3
    assert period.filtered is True
    assert period.from_date == '2024-03-01'


def test_open_ended_window_is_allowed():
    '''Only a lower bound means "from this date onwards".'''
    scoped, _ = apply_date_range(_frame(), '2024-10-01', None)
    assert len(scoped) == 3


def test_malformed_date_is_rejected_with_a_code():
    '''
        The client gets a stable code and renders its own wording; the offending
        value stays in the log, not in the response.
    '''
    with pytest.raises(InvalidInputError) as excinfo:
        apply_date_range(_frame(), '15/03/2024-bad', None)
    assert excinfo.value.detail == AnalyticsError.INVALID_DATE.value


def test_empty_window_is_an_error_not_an_empty_report():
    '''
        A window with no sales must fail loudly: silently returning zeros would
        read as "you sold nothing", which is a different statement.
    '''
    with pytest.raises(InvalidInputError):
        apply_date_range(_frame(), '2030-01-01', '2030-12-31')
