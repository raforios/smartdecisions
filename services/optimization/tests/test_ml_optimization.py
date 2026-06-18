'''
    Unit tests for the ml_optimization algorithm helpers.
'''
import pandas as pd
import pytest

from services.ml_optimization import (
    GeoAnalyzer,
    distance_between_points,
    fiter_order_df,
    hexa_color_generator_list
)


def test_distance_between_points_la_paz() -> None:
    '''
        Geodesic distance between two well-known La Paz coordinates is
        positive and within a reasonable range (< 10 km for nearby points).
    '''
    point_a = (-16.5000, -68.1500)
    point_b = (-16.5050, -68.1450)
    distance = distance_between_points(point_a, point_b)
    assert distance > 0
    assert distance < 10_000


def test_hexa_color_generator_list_returns_unique_colors() -> None:
    '''
        The list helper must return the requested number of distinct colors.
    '''
    colors = hexa_color_generator_list(8)
    assert len(colors) == 8
    assert len(set(colors)) == 8
    assert all(color.startswith('#') and len(color) == 7 for color in colors)


def test_fiter_order_df_filters_and_sorts() -> None:
    '''
        Filter expression keeps the matching rows and sorts by the given column.
    '''
    df = pd.DataFrame({
        'origin': [1, 1, 2, 2, 3],
        'distance': [50.0, 10.0, 30.0, 5.0, 100.0]
    })
    result = fiter_order_df(df['origin'] == 1, 'distance', df)
    assert list(result['distance']) == [10.0, 50.0]


def test_geo_analyzer_distance_matrix_is_symmetric() -> None:
    '''
        The distance matrix is square, symmetric and has zero diagonal.
    '''
    df = pd.DataFrame({
        'latitude':  [-16.5000, -16.5050, -16.5100],
        'longitude': [-68.1500, -68.1450, -68.1400]
    }, index = pd.Index([101, 102, 103], name = 'client_id'))

    analyzer = GeoAnalyzer()
    analyzer.add_locations(df)
    matrix = analyzer.get_distance_matrix()

    assert matrix.shape == (3, 3)
    assert all(matrix.at[client_id, client_id] == 0 for client_id in df.index)
    for orig in df.index:
        for dest in df.index:
            assert matrix.at[orig, dest] == pytest.approx(matrix.at[dest, orig])
