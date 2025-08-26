'''
    Prediction controller
'''

import numpy as np
from services.machine_learning import (
    compute_cost_matrix,
    compute_gradient_matrix,
    gradient_descent_matrix,
    predict_dot,
    compute_cost,
    compute_gradient,
    gradient_descent
)
from services.utils import handle_ml_operation
from schemas.prediction import (
    ComputeCostLinearRequest,
    ComputeCostLinearResponse,
    ComputeGradientLinearRequest,
    ComputeGradientLinearResponse,
    TrainLinearRegressionRequest,
    TrainLinearRegressionResponse,
    PredictLinearRequest,
    PredictLinearResponse
)

@handle_ml_operation
async def compute_cost_linear_regression(
    request_body: ComputeCostLinearRequest
) -> ComputeCostLinearResponse:
    '''
    Controller to calculate the cost of linear regression.
    '''
    x_np = np.array(request_body.x)
    y_np = np.array(request_body.y)
    w_np = np.array(request_body.w)

    if x_np.ndim == 1:
        cost = compute_cost(x_np, y_np, float(w_np), request_body.b)
    else:
        cost = compute_cost_matrix(x_np, y_np, w_np, request_body.b)

    return ComputeCostLinearResponse(cost = float(cost))

@handle_ml_operation
async def compute_gradient_linear_regression(
    request_body: ComputeGradientLinearRequest
) -> ComputeGradientLinearResponse:
    '''
    Controller to calculate the gradient of linear regression.
    '''
    x_np = np.array(request_body.x)
    y_np = np.array(request_body.y)
    w_np = np.array(request_body.w)

    if x_np.ndim == 1:
        dj_dw, dj_db = compute_gradient(x_np, y_np, float(w_np), request_body.b)
    else:
        dj_dw, dj_db = compute_gradient_matrix(x_np, y_np, w_np, request_body.b)

    return ComputeGradientLinearResponse(
        dj_db = float(dj_db),
        dj_dw = dj_dw.tolist() if isinstance(dj_dw, np.ndarray) else float(dj_dw)
    )

@handle_ml_operation
async def train_linear_regression(
    request_body: TrainLinearRegressionRequest
) -> TrainLinearRegressionResponse:
    '''
    Controller for training linear regression using gradient descent.
    '''
    x_np = np.array(request_body.x)
    y_np = np.array(request_body.y)
    w_in_np = np.array(request_body.w_in)

    if x_np.ndim == 1:
        w_final, b_final, j_history, p_history = gradient_descent(
            x_np, y_np, float(w_in_np), request_body.b_in,
            {'alpha': request_body.alpha, 'num_iters': request_body.num_iters}
        )
        p_history_serializable = [[float(w), float(b)] for w, b in p_history]
    else:
        w_final, b_final, hist_dict = gradient_descent_matrix(
            x_np, y_np, w_in_np, request_body.b_in,
            {'alpha': request_body.alpha, 'num_iters': request_body.num_iters}
        )
        j_history = hist_dict['cost']
        p_history_serializable = [
            [w.tolist() if isinstance(w, np.ndarray) else float(w), float(b)]
            for w, b in hist_dict['params']
        ]

    j_history_list = [float(cost) for cost in j_history]

    return TrainLinearRegressionResponse(
        w_final = w_final.tolist() if isinstance(w_final, np.ndarray) else float(w_final),
        b_final = float(b_final),
        J_history = j_history_list,
        p_history = p_history_serializable,
        num_iters = request_body.num_iters
    )

@handle_ml_operation
async def predict_linear_regression(
    request_body: PredictLinearRequest
) -> PredictLinearResponse:
    '''
    Controller for making predictions with a trained linear regression model.
    '''
    x_test_np = np.array(request_body.x_test)
    w_np = np.array(request_body.w)

    predictions_np = predict_dot(x_test_np, w_np, request_body.b)
    predictions_list = predictions_np.tolist()

    return PredictLinearResponse(predictions = predictions_list)
