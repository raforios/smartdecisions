'''
    The training endpoints of the Machine Learning notebooks: each request
    becomes arrays, goes through `machine_learning.py` and comes back as its
    response schema. A one-feature `x` takes the scalar formulas and a matrix
    the vector ones, as the notebooks send both.
'''
import numpy as np

from schemas.classification import (
    ComputeCostLogisticRequest,
    ComputeGradientLogisticRequest,
    ComputeGradientLogisticResponse,
    GradientDescentLogisticRequest,
    GradientDescentLogisticResponse,
    PredictLogisticRequest,
    PredictLogisticResponse,
    SigmoidBatchRequest
)
from schemas.common import NormalizeFeaturesRequest, NormalizeFeaturesResponse
from schemas.prediction import (
    ComputeCostLinearRequest,
    ComputeCostLinearResponse,
    ComputeGradientLinearRequest,
    ComputeGradientLinearResponse,
    PredictLinearRequest,
    PredictLinearResponse,
    TrainLinearRegressionRequest,
    TrainLinearRegressionResponse
)
from services.logger_config import custom_logger as logger
from services.machine_learning import (
    DescentConfig,
    compute_cost,
    compute_cost_logistic,
    compute_cost_matrix,
    compute_gradient,
    compute_gradient_logistic,
    compute_gradient_matrix,
    gradient_descent,
    gradient_descent_logistic,
    gradient_descent_matrix,
    predict_dot,
    predict_logistic,
    sigmoid,
    zscore_normalize_features
)


def _number_or_list(value: np.ndarray | float) -> float | list[float]:
    '''
        A weight as JSON carries it: one number, or one per feature.

        Args:
            value (np.ndarray | float): The weight or weights.

        Returns:
            float | list[float]: The same, serializable.
    '''
    return value.tolist() if isinstance(value, np.ndarray) else float(value)


def linear_cost(request: ComputeCostLinearRequest) -> ComputeCostLinearResponse:
    '''
        The cost of a linear model.

        Args:
            request (ComputeCostLinearRequest): Examples, targets and parameters.

        Returns:
            ComputeCostLinearResponse: The cost.
    '''
    features, targets, weights = np.array(request.x), np.array(request.y), np.array(request.w)
    cost = (compute_cost(features, targets, float(weights), request.b) if features.ndim == 1
            else compute_cost_matrix(features, targets, weights, request.b))
    return ComputeCostLinearResponse(cost = float(cost))


def linear_gradient(request: ComputeGradientLinearRequest) -> ComputeGradientLinearResponse:
    '''
        The gradient of the cost of a linear model.

        Args:
            request (ComputeGradientLinearRequest): Examples, targets and
                parameters.

        Returns:
            ComputeGradientLinearResponse: The gradient for the weights and the bias.
    '''
    features, targets, weights = np.array(request.x), np.array(request.y), np.array(request.w)
    weights_step, bias_step = (
        compute_gradient(features, targets, float(weights), request.b) if features.ndim == 1
        else compute_gradient_matrix(features, targets, weights, request.b))
    return ComputeGradientLinearResponse(dj_db = float(bias_step),
                                         dj_dw = _number_or_list(weights_step))


def train_linear(request: TrainLinearRegressionRequest) -> TrainLinearRegressionResponse:
    '''
        Fits a linear model by gradient descent.

        Args:
            request (TrainLinearRegressionRequest): Examples, targets, starting
                parameters, learning rate and iterations.

        Returns:
            TrainLinearRegressionResponse: The final parameters and the history.
    '''
    features, targets = np.array(request.x), np.array(request.y)
    weights = np.array(request.w_in)
    config = DescentConfig(alpha = request.alpha, num_iters = request.num_iters)
    if features.ndim == 1:
        final_weights, final_bias, costs, parameters = gradient_descent(
            features, targets, float(weights), request.b_in, config)
    else:
        final_weights, final_bias, history = gradient_descent_matrix(
            features, targets, weights, request.b_in, config)
        costs, parameters = history['cost'], history['params']
    return TrainLinearRegressionResponse(
        w_final = _number_or_list(final_weights),
        b_final = float(final_bias),
        J_history = [float(cost) for cost in costs],
        p_history = [[_number_or_list(step_weights), float(step_bias)]
                     for step_weights, step_bias in parameters],
        num_iters = request.num_iters
    )


def predict_linear(request: PredictLinearRequest) -> PredictLinearResponse:
    '''
        The predictions of a trained linear model.

        Args:
            request (PredictLinearRequest): The examples and the parameters.

        Returns:
            PredictLinearResponse: One prediction per example.
    '''
    predictions = predict_dot(np.array(request.x_test), np.array(request.w), request.b)
    return PredictLinearResponse(predictions = predictions.tolist())


def normalize(request: NormalizeFeaturesRequest) -> NormalizeFeaturesResponse:
    '''
        The features normalized by column.

        Args:
            request (NormalizeFeaturesRequest): The feature matrix.

        Returns:
            NormalizeFeaturesResponse: The normalized matrix, the mean and the
                deviation of each column.
    '''
    normalized, mean, deviation = zscore_normalize_features(np.array(request.x_matrix))
    message = f'Z-score normalization of a {normalized.shape} matrix.'
    logger.info(message)
    return NormalizeFeaturesResponse(x_norm = normalized.tolist(), mu = mean.tolist(),
                                     sigma = deviation.tolist())


def sigmoid_batch(request: SigmoidBatchRequest) -> list[float]:
    '''
        The sigmoid of each value. A bare list: the notebooks read it so.

        Args:
            request (SigmoidBatchRequest): The values.

        Returns:
            list[float]: sigmoid of each value.
    '''
    return sigmoid(np.array(request.z_values)).tolist()


def logistic_cost(request: ComputeCostLogisticRequest) -> float:
    '''
        The log loss of a logistic model. A bare number: the notebooks read
        it so.

        Args:
            request (ComputeCostLogisticRequest): Examples, targets and parameters.

        Returns:
            float: The mean log loss.
    '''
    return compute_cost_logistic(np.array(request.x_matrix), np.array(request.y),
                                 np.array(request.w), request.b)


def logistic_gradient(
    request: ComputeGradientLogisticRequest
) -> ComputeGradientLogisticResponse:
    '''
        The gradient of the log loss of a logistic model.

        Args:
            request (ComputeGradientLogisticRequest): Examples, targets and
                parameters.

        Returns:
            ComputeGradientLogisticResponse: The gradient for the weights and the bias.
    '''
    weights_step, bias_step = compute_gradient_logistic(
        np.array(request.x_matrix), np.array(request.y), np.array(request.w), request.b)
    return ComputeGradientLogisticResponse(dj_db = float(bias_step),
                                           dj_dw = weights_step.tolist())


def train_logistic(request: GradientDescentLogisticRequest) -> GradientDescentLogisticResponse:
    '''
        Fits a logistic model by gradient descent.

        Args:
            request (GradientDescentLogisticRequest): Examples, targets,
                starting parameters, learning rate and iterations.

        Returns:
            GradientDescentLogisticResponse: The final parameters and the history.
    '''
    weights, bias, costs, parameters = gradient_descent_logistic(
        np.array(request.x_matrix), np.array(request.y), np.array(request.w_in), request.b_in,
        DescentConfig(alpha = request.alpha, num_iters = request.num_iters))
    return GradientDescentLogisticResponse(
        w = weights.tolist(), b = float(bias), J_history = [float(cost) for cost in costs],
        p_history = [[step_weights.tolist(), float(step_bias)]
                     for step_weights, step_bias in parameters]
    )


def predict_classes(request: PredictLogisticRequest) -> PredictLogisticResponse:
    '''
        The class of each example under a trained logistic model.

        Args:
            request (PredictLogisticRequest): The examples and the parameters.

        Returns:
            PredictLogisticResponse: 0 or 1 per example.
    '''
    predictions = predict_logistic(np.array(request.x_matrix), np.array(request.w), request.b)
    return PredictLogisticResponse(predictions = predictions.tolist())
