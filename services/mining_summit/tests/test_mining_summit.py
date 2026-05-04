'''
    services/mining_summit/tests/test_mining_summit.py

    Smoke tests for the Mining Summit business logic. They exercise the
    aggregation helper without requiring AWS access; integration tests for the
    DynamoDB-bound endpoints belong in the integration test suite.
'''
from services.reports import _aggregate_by_dimension


def test_aggregate_by_dimension_counts_and_percentages():
    '''
        Aggregation must group by the dimension and produce percentages whose
        sum is 100 (modulo rounding) when at least one item is present.
    '''
    items = [
        {'department': 'La Paz'},
        {'department': 'La Paz'},
        {'department': 'Cochabamba'},
        {'department': ''},
    ]
    result = _aggregate_by_dimension(items, 'department')

    labels = {row['label']: row for row in result}
    assert labels['La Paz']['count'] == 2
    assert labels['Cochabamba']['count'] == 1
    assert labels['Sin especificar']['count'] == 1

    total_pct = sum(row['percentage'] for row in result)
    assert abs(total_pct - 100.0) < 0.5


def test_aggregate_by_dimension_empty_returns_empty_list():
    '''
        With no items the aggregation must return an empty list (no division).
    '''
    assert _aggregate_by_dimension([], 'company') == []
