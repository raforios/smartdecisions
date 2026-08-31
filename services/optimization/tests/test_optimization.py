'''
    Unit tests for the route planner: clustering, balancing and stop ordering.
'''
import numpy as np
import pandas as pd
import pytest

from schemas.optimization import OptimizationError
from services.exceptions import InvalidInputError
from services.optimization import (
    assign_days,
    build_client_points,
    haversine_matrix,
    order_stops,
    plan_day
)


def _sales_frame() -> pd.DataFrame:
    '''
        Six clients in two tight geographic groups, with different spend.

        Returns:
            pd.DataFrame: Normalized sales rows.
    '''
    rows = []
    groups = [(-16.50, -68.12), (-16.54, -68.07)]
    for group_index, (lat, lon) in enumerate(groups):
        for offset in range(3):
            client = f'C{group_index}{offset}'
            rows.append({
                'order_id': f'F-{client}', 'pos_id': client,
                'pos_name': f'Tienda {client}', 'seller': 'Ana',
                'date': pd.Timestamp('2024-01-10'),
                'latitude': lat + offset * 0.002, 'longitude': lon + offset * 0.002,
                'total_amount': 100.0 * (offset + 1) * (group_index + 1),
            })
    return pd.DataFrame(rows)


def test_distance_matrix_is_symmetric_with_a_zero_diagonal():
    '''A distance matrix that fails this makes every tour length meaningless.'''
    points = np.array([[-16.50, -68.12], [-16.54, -68.07], [-16.52, -68.10]])
    matrix = haversine_matrix(points)
    assert np.allclose(matrix, matrix.T)
    assert np.allclose(np.diag(matrix), 0.0)


def test_known_distance_is_accurate():
    '''
        Two points one degree of latitude apart are ~111 km. Anchors the
        haversine implementation to a figure that can be checked by hand.
    '''
    matrix = haversine_matrix(np.array([[0.0, 0.0], [1.0, 0.0]]))
    assert 110_000 < matrix[0][1] < 112_000


def test_clients_are_collapsed_to_one_geolocated_row_each():
    '''Sales rows become visits: one row per client, carrying what it is worth.'''
    clients = build_client_points(_sales_frame())
    assert len(clients) == 6
    assert set(clients['segment']) <= {'HIGH', 'MEDIUM', 'LOW'}
    assert clients["amount"].sum() == pytest.approx(1800.0)


def test_missing_coordinates_are_reported_with_a_code():
    '''
        A file without coordinates cannot produce a route: the client gets a
        stable code and words it, instead of a KeyError leaking out.
    '''
    frame = _sales_frame().drop(columns = ['latitude', 'longitude'])
    with pytest.raises(InvalidInputError) as excinfo:
        build_client_points(frame)
    assert excinfo.value.detail == OptimizationError.MISSING_COORDINATES.value


def test_days_are_derived_from_geography():
    '''
        Two tight groups split into two days, each holding one group — the point
        of deriving the day from where the clients are.
    '''
    clients = assign_days(build_client_points(_sales_frame()), 2)
    grouped = clients.groupby('day')['client_id'].apply(lambda ids: {name[:2] for name in ids})
    assert len(grouped) == 2
    assert all(len(prefixes) == 1 for prefixes in grouped)


def test_days_are_balanced():
    '''
        Plain k-means produced days of 8 and 97 stops on real data. No day may
        carry more than one extra stop over the even split.
    '''
    rng = np.random.default_rng(3)
    rows = [
        {
            'order_id': f'F{index}', 'pos_id': f'C{index}',
            'pos_name': f'Tienda {index}', 'date': pd.Timestamp('2024-01-10'),
            'latitude': -16.5 + rng.normal(0, 0.05),
            'longitude': -68.1 + rng.normal(0, 0.05),
            'total_amount': 100.0,
        }
        for index in range(60)
    ]
    clients = assign_days(build_client_points(pd.DataFrame(rows)), 5)
    sizes = clients.groupby('day').size()
    assert sizes.max() - sizes.min() <= 1


def test_two_opt_never_lengthens_the_route():
    '''
        Regression: 2-opt was optimising a closed loop while the route is an
        open path, so it could return a tour longer than the greedy one.
    '''
    rng = np.random.default_rng(11)
    points = np.column_stack([
        -16.5 + rng.normal(0, 0.02, 40), -68.1 + rng.normal(0, 0.02, 40)
    ])
    distances = haversine_matrix(points)

    def length(order):
        return sum(distances[order[i]][order[i + 1]] for i in range(len(order) - 1))

    greedy = list(range(len(points)))
    assert length(order_stops(points)) <= length(greedy)


def test_plan_day_returns_numbered_stops_with_their_value():
    '''Each stop tells the rep who it is, what they buy and how valuable.'''
    clients = assign_days(build_client_points(_sales_frame()), 2)
    stops = plan_day(clients, 1)
    assert stops
    assert [stop.stop_order for stop in stops] == list(range(1, len(stops) + 1))
    assert all(stop.client and stop.segment for stop in stops)
