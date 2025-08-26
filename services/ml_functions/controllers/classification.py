'''
    Classification controller
'''
import numpy as np
from services.logger_config import custom_logger as logger
from services.utils import handle_ml_operation
from services.machine_learning import (
    sigmoid,
    compute_cost_logistic,
    compute_gradient_logistic,
    gradient_descent_logistic,
    predict_logistic
)
from schemas.classification import (
    SigmoidBatchRequest,
    ComputeCostLogisticRequest,
    ComputeGradientLogisticRequest,
    GradientDescentLogisticRequest,
    PredictLogisticRequest,
    PredictLogisticResponse
)

@handle_ml_operation
async def calculating_sigmoid(request_body: SigmoidBatchRequest):
    '''
    Calculates the sigmoid function for a given input value or array of values.
    '''
    # Se convierte a una lista para asegurar la serialización correcta
    response = sigmoid(np.array(request_body.z_values)).tolist()
    message = 'Batch sigmoid calculation completed.'
    logger.info(message)
    return response

@handle_ml_operation
async def calculating_cost_logistic(
    request_body: ComputeCostLogisticRequest
) -> float:
    '''
    Calculates the logistic regression cost using the compute_cost_logistic.
    '''
    cost = compute_cost_logistic(
        np.array(request_body.x_matrix),
        np.array(request_body.y),
        np.array(request_body.w),
        request_body.b
    )
    message = f'Logistic cost calculated: {cost}'
    logger.info(message)
    return float(cost)

@handle_ml_operation
async def calculating_gradient_logistic(
    request_body: ComputeGradientLogisticRequest
) -> dict:
    '''
    Calculates the logistic regression gradient using the compute_gradient_logistic.
    '''
    dj_dw, dj_db = compute_gradient_logistic(
        np.array(request_body.x_matrix),
        np.array(request_body.y),
        np.array(request_body.w),
        request_body.b
    )
    message = f'Logistic gradient calculated: dj_db = {dj_db}, dj_dw = {dj_dw.tolist()}'
    logger.info(message)

    return {"dj_db": float(dj_db), "dj_dw": dj_dw.tolist()}

@handle_ml_operation
async def performing_gradient_descent_logistic(
    request_body: GradientDescentLogisticRequest
) -> dict:
    '''
    Performs logistic regression gradient descent to find optimal parameters (w, b).
    '''
    w_final, b_final, j_history, p_history = gradient_descent_logistic(
        np.array(request_body.x_matrix),
        np.array(request_body.y),
        np.array(request_body.w_in),
        request_body.b_in,
        {'alpha': request_body.alpha, 'num_iters': request_body.num_iters}
    )

    p_history_serializable = []
    for w_val, b_val in p_history:
        p_history_serializable.append([w_val.tolist(), float(b_val)])

    response_data = {
        'w': w_final.tolist(),
        'b': float(b_final),
        'J_history': [float(cost) for cost in j_history],
        'p_history': p_history_serializable
    }
    message = f'Logistic gradient descent completed. Final w: {w_final.tolist()}, b: {b_final}'
    logger.info(message)
    return response_data

@handle_ml_operation
async def predicting_logistic_classification(
    request_body: PredictLogisticRequest
) -> PredictLogisticResponse:
    '''
    Performs logistic regression prediction using predict_logistic.
    '''
    predictions_np = predict_logistic(
        np.array(request_body.x_matrix),
        np.array(request_body.w),
        request_body.b
    )
    predictions_list = predictions_np.tolist()

    message = f'Logistic prediction completed. Predicted labels: {predictions_list}'
    logger.info(message)

    return PredictLogisticResponse(predictions = predictions_list)
