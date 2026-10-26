'''
    Tests for the clusters and the visit order.

    They import only the pure module: the CI runs this service's tests with
    no .env.
'''
import numpy as np
import pytest

from services.routing import ClusterSpec, cluster_points, haversine_matrix, order_points

SPEC = ClusterSpec(clusters = 2, seed = 7, iterations = 60)


def test_the_distance_of_a_degree_of_latitude():
    '''One degree of latitude is about 111 km, and the matrix is symmetric.'''
    matrix = haversine_matrix(np.array([[0.0, 0.0], [1.0, 0.0]]))
    assert matrix[0][1] == pytest.approx(111_195, rel = 1e-3)
    assert matrix[0][1] == matrix[1][0] and matrix[0][0] == 0


def test_two_neighbourhoods_make_two_groups():
    '''Points around two far centres split by centre, the same every time.'''
    north = [[-16.50 + i * 0.001, -68.10] for i in range(5)]
    south = [[-16.60 + i * 0.001, -68.20] for i in range(5)]
    labels = cluster_points(north + south, SPEC)
    assert len(set(labels[:5])) == 1 and len(set(labels[5:])) == 1
    assert labels[0] != labels[5]
    assert cluster_points(north + south, SPEC) == labels


def test_no_group_passes_an_even_share():
    '''Nine points piled on one spot and one far away: five and five.'''
    points = [[-16.5, -68.1]] * 9 + [[-17.5, -66.1]]
    labels = cluster_points(points, SPEC)
    assert sorted(np.bincount(labels).tolist()) == [5, 5]


def test_the_order_starts_at_the_first_stop_and_has_no_crossings():
    '''Stops on a line come back in line order, from the first one.'''
    points = [[0.0, 0.0], [0.0, 0.3], [0.0, 0.1], [0.0, 0.2]]
    assert order_points(points, 8) == [0, 2, 3, 1]


def test_two_stops_are_left_as_they_came():
    '''There is nothing to order with two stops.'''
    assert order_points([[0.0, 0.0], [1.0, 1.0]], 8) == [0, 1]
