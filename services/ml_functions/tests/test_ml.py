'''
    services/ml_functions/tests/test_ml.py

    Pure tests of the regressions: known results on small series, with no
    configuration, because the CI of GitHub Actions runs them with no .env.
'''
import math

import numpy as np
import pytest

from services.machine_learning import (
    compute_cost,
    compute_cost_logistic,
    compute_cost_matrix,
    compute_gradient,
    compute_gradient_logistic,
    compute_gradient_matrix,
    gradient_descent,
    gradient_descent_logistic,
    gradient_descent_matrix,
    predict_logistic,
    sigmoid,
    zscore_normalize_features
)

# y = 2x + 1, the line every linear test must recover.
X_LINE = np.array([1.0, 2.0, 3.0, 4.0])
Y_LINE = 2 * X_LINE + 1
TRAINING = {'alpha': 0.05, 'num_iters': 5000}


def test_cost_is_zero_on_the_exact_line() -> None:
    '''The squared error is zero when the model is the line itself.'''
    assert compute_cost(X_LINE, Y_LINE, 2, 1) == pytest.approx(0)


def test_cost_matches_the_formula() -> None:
    '''With w = b = 0 the cost is the sum of y squared over 2m.'''
    assert compute_cost(X_LINE, Y_LINE, 0, 0) == pytest.approx(
        float(np.sum(Y_LINE ** 2)) / (2 * len(Y_LINE)))


def test_gradient_is_zero_at_the_minimum() -> None:
    '''At the exact line there is nothing left to descend.'''
    dj_dw, dj_db = compute_gradient(X_LINE, Y_LINE, 2, 1)
    assert dj_dw == pytest.approx(0)
    assert dj_db == pytest.approx(0)


def test_gradient_descent_finds_the_line() -> None:
    '''Starting from zero, the descent recovers w = 2 and b = 1.'''
    w, b, history, _ = gradient_descent(X_LINE, Y_LINE, 0, 0, TRAINING)
    assert w == pytest.approx(2, abs = 1e-2)
    assert b == pytest.approx(1, abs = 1e-2)
    assert history[-1] < history[0]


def test_matrix_versions_agree_with_the_scalar_ones() -> None:
    '''One feature in a matrix gives the same cost and gradient as a scalar.'''
    x_matrix = X_LINE.reshape(-1, 1)
    w = np.array([0.5])
    assert compute_cost_matrix(x_matrix, Y_LINE, w, 0.3) == pytest.approx(
        compute_cost(X_LINE, Y_LINE, 0.5, 0.3))
    dj_dw, dj_db = compute_gradient_matrix(x_matrix, Y_LINE, w, 0.3)
    scalar_dw, scalar_db = compute_gradient(X_LINE, Y_LINE, 0.5, 0.3)
    assert dj_dw[0] == pytest.approx(scalar_dw)
    assert dj_db == pytest.approx(scalar_db)


def test_matrix_gradient_descent_finds_the_plane() -> None:
    '''Two features: y = 3a - 2b + 4 is recovered.'''
    x_matrix = np.array([[1.0, 2.0], [2.0, 1.0], [3.0, 4.0], [4.0, 3.0], [5.0, 5.0]])
    y = 3 * x_matrix[:, 0] - 2 * x_matrix[:, 1] + 4
    w, b, _ = gradient_descent_matrix(x_matrix, y, np.zeros(2), 0, TRAINING)
    assert w == pytest.approx([3, -2], abs = 5e-2)
    assert b == pytest.approx(4, abs = 1e-1)


def test_zscore_centres_and_scales_each_column() -> None:
    '''Every column ends with mean 0 and standard deviation 1.'''
    x_norm, mu, sigma = zscore_normalize_features(np.array([[1.0, 10.0], [3.0, 30.0]]))
    assert mu == pytest.approx([2, 20])
    assert sigma == pytest.approx([1, 10])
    assert x_norm.mean(axis = 0) == pytest.approx([0, 0])
    assert x_norm.std(axis = 0) == pytest.approx([1, 1])


def test_sigmoid_limits() -> None:
    '''Half at zero, near 0 and 1 far away, symmetric around zero.'''
    values = sigmoid(np.array([-20.0, 0.0, 20.0]))
    assert values[1] == pytest.approx(0.5)
    assert values[0] == pytest.approx(0, abs = 1e-8)
    assert values[2] == pytest.approx(1, abs = 1e-8)


def test_logistic_cost_with_no_information() -> None:
    '''With w = b = 0 every prediction is one half, and the cost is log 2.'''
    x_matrix = np.array([[1.0], [2.0]])
    assert compute_cost_logistic(x_matrix, np.array([0, 1]), np.zeros(1), 0) == \
        pytest.approx(math.log(2))


def test_logistic_gradient_points_towards_the_labels() -> None:
    '''With balanced labels and no model, the bias has nothing to correct.'''
    x_matrix = np.array([[-1.0], [1.0]])
    dj_dw, dj_db = compute_gradient_logistic(x_matrix, np.array([0, 1]), np.zeros(1), 0)
    assert dj_db == pytest.approx(0)
    assert dj_dw[0] < 0


def test_logistic_training_separates_the_classes() -> None:
    '''Below 2.5 is 0, above is 1: trained, the model predicts every label.'''
    x_matrix = np.array([[0.5], [1.0], [2.0], [3.0], [4.0], [4.5]])
    y = np.array([0, 0, 0, 1, 1, 1])
    w, b, history, _ = gradient_descent_logistic(x_matrix, y, np.zeros(1), 0, TRAINING)
    assert list(predict_logistic(x_matrix, w, b)) == list(y)
    assert history[-1] < history[0]


def test_predict_logistic_threshold_is_one_half() -> None:
    '''Exactly one half counts as 1.'''
    predictions = predict_logistic(np.array([[0.0], [1.0], [-1.0]]), np.array([5.0]), 0)
    assert list(predictions) == [1, 1, 0]
