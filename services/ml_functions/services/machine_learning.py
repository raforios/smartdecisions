'''
    Linear, multiple linear and logistic regression trained by gradient
    descent: the functions the Machine Learning training notebooks call
    through the API (Rafael, 5-nov-2026: they are kept for the courses).

    The names of the API fields (x, y, w, b, J_history) are the notebooks'
    contract; inside, the arrays carry what they mean.
'''
import copy
import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from core.logger_config import custom_logger as logger

# The history keeps at most this many snapshots, so a long run does not
# exhaust memory.
MAX_SNAPSHOTS = 10000
# How many progress lines a run logs.
PROGRESS_LINES = 10
# exp(-z) overflows past this magnitude.
SIGMOID_CLIP = 500
# A logistic run stops when the cost improves by less than this.
CONVERGENCE_EPSILON = 1e-6
# Probability from which a logistic prediction is the positive class.
DECISION_THRESHOLD = 0.5


@dataclass(frozen = True)
class DescentConfig:
    '''
        How a gradient descent runs.
    '''
    alpha: float
    num_iters: int


def _snapshot_interval(num_iters: int) -> float:
    '''
        Every how many iterations a run keeps a snapshot of its cost and
        parameters.

        Args:
            num_iters (int): Iterations of the run.

        Returns:
            float: The interval.
    '''
    return np.ceil(num_iters / MAX_SNAPSHOTS)


def _logs_progress(
    iteration: int,
    num_iters: int
) -> bool:
    '''
        Whether this iteration logs its progress: about ten times per run.

        Args:
            iteration (int): The iteration, from zero.
            num_iters (int): Iterations of the run.

        Returns:
            bool: True when it logs.
    '''
    return iteration % math.ceil(num_iters / PROGRESS_LINES) == 0


# ----------------------------------------------------------------
# LINEAR REGRESSION
# ----------------------------------------------------------------

def compute_cost(
    features: np.ndarray,
    targets: np.ndarray,
    weight: float,
    bias: float
) -> float:
    '''
        The cost of a one-feature linear model over its examples.

        Args:
            features (np.ndarray): Shape (m,), one value per example.
            targets (np.ndarray): Shape (m,), the target of each example.
            weight (float): The model's weight.
            bias (float): The model's bias.

        Returns:
            float: The mean squared error, halved.
    '''
    examples = features.shape[0]
    predictions = weight * features + bias
    return np.sum((predictions - targets) ** 2) / (2 * examples)


def compute_gradient(
    features: np.ndarray,
    targets: np.ndarray,
    weight: float,
    bias: float
) -> tuple[float, float]:
    '''
        The gradient of the cost of a one-feature linear model.

        Args:
            features (np.ndarray): Shape (m,), one value per example.
            targets (np.ndarray): Shape (m,), the target of each example.
            weight (float): The model's weight.
            bias (float): The model's bias.

        Returns:
            tuple[float, float]: The gradient for the weight and for the bias.
    '''
    examples = features.shape[0]
    errors = weight * features + bias - targets
    return float(np.sum(errors * features) / examples), float(np.sum(errors) / examples)


def gradient_descent(
    features: np.ndarray,
    targets: np.ndarray,
    weight: float,
    bias: float,
    config: DescentConfig
) -> tuple[float, float, list[float], list[list[float]]]:
    '''
        Fits a one-feature linear model by gradient descent.

        Args:
            features (np.ndarray): Shape (m,), one value per example.
            targets (np.ndarray): Shape (m,), the target of each example.
            weight (float): The starting weight.
            bias (float): The starting bias.
            config (DescentConfig): Learning rate and iterations.

        Returns:
            tuple[float, float, list[float], list[list[float]]]: The final
                weight and bias, and the history of the cost and of [weight,
                bias].
    '''
    costs: list[float] = []
    parameters: list[list[float]] = []
    interval = _snapshot_interval(config.num_iters)
    for iteration in range(config.num_iters):
        weight_step, bias_step = compute_gradient(features, targets, weight, bias)
        bias -= config.alpha * bias_step
        weight -= config.alpha * weight_step
        if iteration == 0 or iteration % interval == 0:
            costs.append(compute_cost(features, targets, weight, bias))
            parameters.append([weight, bias])
        if _logs_progress(iteration, config.num_iters):
            message = (f'Iteration {iteration:9d}: cost {costs[-1]:0.2f}, w {weight:0.2f}, '
                       f'b {bias:0.2f}, dj_dw {weight_step:0.2f}, dj_db {bias_step:0.2f}.')
            logger.info(message)
    message = f'Linear descent finished after {config.num_iters} iterations: cost {costs[-1]:0.2f}.'
    logger.info(message)
    return weight, bias, costs, parameters


# ----------------------------------------------------------------
# MULTIPLE LINEAR REGRESSION
# ----------------------------------------------------------------

def predict_dot(
    features: np.ndarray,
    weights: np.ndarray,
    bias: float
) -> np.ndarray:
    '''
        The predictions of a linear model.

        Args:
            features (np.ndarray): Shape (m, n) or (n,), the examples.
            weights (np.ndarray): Shape (n,), one weight per feature.
            bias (float): The model's bias.

        Returns:
            np.ndarray: One prediction per example.
    '''
    return np.dot(features, weights) + bias


def compute_cost_matrix(
    features: np.ndarray,
    targets: np.ndarray,
    weights: np.ndarray,
    bias: float
) -> float:
    '''
        The cost of a linear model over its examples.

        Args:
            features (np.ndarray): Shape (m, n), m examples with n features.
            targets (np.ndarray): Shape (m,), the target of each example.
            weights (np.ndarray): Shape (n,), one weight per feature.
            bias (float): The model's bias.

        Returns:
            float: The mean squared error, halved.
    '''
    examples, _ = features.shape
    return np.sum((features @ weights + bias - targets) ** 2) / (2 * examples)


def compute_gradient_matrix(
    features: np.ndarray,
    targets: np.ndarray,
    weights: np.ndarray,
    bias: float
) -> tuple[np.ndarray, float]:
    '''
        The gradient of the cost of a linear model.

        Args:
            features (np.ndarray): Shape (m, n), m examples with n features.
            targets (np.ndarray): Shape (m,), the target of each example.
            weights (np.ndarray): Shape (n,), one weight per feature.
            bias (float): The model's bias.

        Returns:
            tuple[np.ndarray, float]: The gradient for each weight and for the
                bias.
    '''
    examples, _ = features.shape
    errors = features @ weights + bias - targets
    return (features.T @ errors) / examples, float(np.sum(errors) / examples)


def gradient_descent_matrix(
    features: np.ndarray,
    targets: np.ndarray,
    weights: np.ndarray,
    bias: float,
    config: DescentConfig
) -> tuple[np.ndarray, float, dict[str, list[Any]]]:
    '''
        Fits a linear model by batch gradient descent.

        Args:
            features (np.ndarray): Shape (m, n), m examples with n features.
            targets (np.ndarray): Shape (m,), the target of each example.
            weights (np.ndarray): Shape (n,), the starting weights.
            bias (float): The starting bias.
            config (DescentConfig): Learning rate and iterations.

        Returns:
            tuple[np.ndarray, float, dict[str, list[Any]]]: The final weights
                and bias, and the history: 'cost', 'params', 'grads', 'iter'.
    '''
    # A copy: the caller's array is not moved under it.
    weights = copy.deepcopy(weights)
    history: dict[str, list[Any]] = {'cost': [], 'params': [], 'grads': [], 'iter': []}
    interval = _snapshot_interval(config.num_iters)
    for iteration in range(config.num_iters):
        weights_step, bias_step = compute_gradient_matrix(features, targets, weights, bias)
        weights = weights - config.alpha * weights_step
        bias = bias - config.alpha * bias_step
        if iteration == 0 or iteration % interval == 0:
            history['cost'].append(compute_cost_matrix(features, targets, weights, bias))
            history['params'].append([weights, bias])
            history['grads'].append([weights_step, bias_step])
            history['iter'].append(iteration)
        if _logs_progress(iteration, config.num_iters):
            message = (f'Iteration {iteration:9d}: cost {history["cost"][-1]:0.2f}, '
                       f'w {weights}, b {bias:0.2f}.')
            logger.info(message)
    message = (f'Multiple linear descent finished after {config.num_iters} iterations: '
               f'cost {history["cost"][-1]:0.2f}.')
    logger.info(message)
    return weights, bias, history


# ----------------------------------------------------------------
# Z-SCORE NORMALIZATION
# ----------------------------------------------------------------

def zscore_normalize_features(
    features: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    '''
        The features normalized by column to mean 0 and deviation 1.

        Args:
            features (np.ndarray): Shape (m, n), m examples with n features.

        Returns:
            tuple[np.ndarray, np.ndarray, np.ndarray]: The normalized features,
                the mean and the standard deviation of each column.
    '''
    mean = np.mean(features, axis = 0)
    deviation = np.std(features, axis = 0)
    return (features - mean) / deviation, mean, deviation


# ----------------------------------------------------------------
# LOGISTIC REGRESSION
# ----------------------------------------------------------------

def sigmoid(values: np.ndarray) -> np.ndarray:
    '''
        The logistic function: any real number into the range 0 to 1. The
        input is clipped so exp(-z) cannot overflow.

        Args:
            values (np.ndarray): A scalar or an array of any shape.

        Returns:
            np.ndarray: sigmoid of each value, in the input's shape.
    '''
    return 1 / (1 + np.exp(-np.clip(values, -SIGMOID_CLIP, SIGMOID_CLIP)))


def compute_cost_logistic(
    features: np.ndarray,
    targets: np.ndarray,
    weights: np.ndarray,
    bias: float
) -> float:
    '''
        The log loss of a logistic model over its examples.

        Args:
            features (np.ndarray): Shape (m, n), m examples with n features.
            targets (np.ndarray): Shape (m,), 0 or 1 for each example.
            weights (np.ndarray): Shape (n,), one weight per feature.
            bias (float): The model's bias.

        Returns:
            float: The mean log loss.
    '''
    examples, _ = features.shape
    probabilities = sigmoid(features @ weights + bias)
    losses = -targets * np.log(probabilities) - (1 - targets) * np.log(1 - probabilities)
    return float(np.sum(losses) / examples)


def compute_gradient_logistic(
    features: np.ndarray,
    targets: np.ndarray,
    weights: np.ndarray,
    bias: float
) -> tuple[np.ndarray, float]:
    '''
        The gradient of the log loss of a logistic model.

        Args:
            features (np.ndarray): Shape (m, n), m examples with n features.
            targets (np.ndarray): Shape (m,), 0 or 1 for each example.
            weights (np.ndarray): Shape (n,), one weight per feature.
            bias (float): The model's bias.

        Returns:
            tuple[np.ndarray, float]: The gradient for each weight and for the
                bias.
    '''
    examples, _ = features.shape
    errors = sigmoid(features @ weights + bias) - targets
    return (features.T @ errors) / examples, float(np.sum(errors) / examples)


def gradient_descent_logistic(
    features: np.ndarray,
    targets: np.ndarray,
    weights: np.ndarray,
    bias: float,
    config: DescentConfig
) -> tuple[np.ndarray, float, list[float], list[list[Any]]]:
    '''
        Fits a logistic model by batch gradient descent, stopping early when
        the cost stops improving.

        Args:
            features (np.ndarray): Shape (m, n), m examples with n features.
            targets (np.ndarray): Shape (m,), 0 or 1 for each example.
            weights (np.ndarray): Shape (n,), the starting weights.
            bias (float): The starting bias.
            config (DescentConfig): Learning rate and iterations.

        Returns:
            tuple[np.ndarray, float, list[float], list[list[Any]]]: The final
                weights and bias, and the history of the cost and of [weights,
                bias].
    '''
    costs: list[float] = []
    parameters: list[list[Any]] = []
    previous_cost = float('inf')
    interval = _snapshot_interval(config.num_iters)
    for iteration in range(config.num_iters):
        weights_step, bias_step = compute_gradient_logistic(features, targets, weights, bias)
        weights = weights - config.alpha * weights_step
        bias = bias - config.alpha * bias_step
        current_cost = compute_cost_logistic(features, targets, weights, bias)
        if iteration == 0 or iteration % interval == 0:
            costs.append(current_cost)
            parameters.append([weights, bias])
        if iteration > 0 and (abs(previous_cost - current_cost) < CONVERGENCE_EPSILON
                              or current_cost > previous_cost):
            message = (f'Logistic descent converged at iteration {iteration + 1}: cost '
                       f'{current_cost:.6f}, previous {previous_cost:.6f}.')
            logger.info(message)
            break
        previous_cost = current_cost
        if _logs_progress(iteration, config.num_iters):
            message = f'Iteration {iteration:9d}: cost {costs[-1]:0.2f}, b {bias:0.2f}.'
            logger.info(message)
    return weights, bias, costs, parameters


def predict_logistic(
    features: np.ndarray,
    weights: np.ndarray,
    bias: float
) -> np.ndarray:
    '''
        The class of each example under a logistic model.

        Args:
            features (np.ndarray): Shape (m, n), m examples with n features.
            weights (np.ndarray): Shape (n,), one weight per feature.
            bias (float): The model's bias.

        Returns:
            np.ndarray: Shape (m,), 1 where the probability reaches the
                threshold, 0 elsewhere.
    '''
    return (sigmoid(features @ weights + bias) >= DECISION_THRESHOLD).astype(int)
