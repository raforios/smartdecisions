'''
    Classification controller
'''

import numpy as np
from services.logger_config import custom_logger as logger
from services.utils import handle_operation
from services.machine_learning import (
    sigmoid,
    compute_cost_logistic,
    compute_gradient_logistic,
    gradient_descent_logistic,
    predict_logistic
)
from services.classification import association_rules, rank_tiers
from schemas.classification import (
    AssociationRule,
    AssociationRulesRequest,
    AssociationRulesResponse,
    TiersRequest,
    TiersResponse,
    SigmoidBatchRequest,
    ComputeCostLogisticRequest,
    ComputeGradientLogisticRequest,
    GradientDescentLogisticRequest,
    PredictLogisticRequest,
    PredictLogisticResponse
)

@handle_operation(exc_type = (ValueError, TypeError))
async def calculating_sigmoid(
    request_body: SigmoidBatchRequest
) -> list[float]:
    '''
    Calculates the sigmoid function for a given input value or array of values.
    '''
    response = sigmoid(np.array(request_body.z_values)).tolist()
    message = 'Batch sigmoid calculation completed.'
    logger.info(message)
    return response

@handle_operation(exc_type = (ValueError, TypeError))
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

@handle_operation(exc_type = (ValueError, TypeError))
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

@handle_operation(exc_type = (ValueError, TypeError))
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

@handle_operation(exc_type = (ValueError, TypeError))
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


@handle_operation(exc_type = (ValueError, TypeError))
async def ranking_tiers(request_body: TiersRequest) -> TiersResponse:
    '''
    Controller splitting the values in tiers by their place in the ranking.
    '''
    tiers = rank_tiers(request_body.values, request_body.cuts)
    message = f'{len(tiers)} value(s) split in {len(request_body.cuts) + 1} tiers.'
    logger.info(message)
    return TiersResponse(tiers = tiers)


@handle_operation(exc_type = (ValueError, TypeError))
async def mining_association_rules(
    request_body: AssociationRulesRequest
) -> AssociationRulesResponse:
    '''
    Controller mining the association rules of the transactions (Apriori).
    '''
    rules = association_rules(request_body.transactions, request_body.min_support,
                              request_body.min_lift)
    message = (f'{len(rules)} association rule(s) from '
               f'{len(request_body.transactions)} transaction(s).')
    logger.info(message)
    return AssociationRulesResponse(
        rules = [AssociationRule(antecedents = list(rule.antecedents),
                                 consequents = list(rule.consequents),
                                 support = rule.support, confidence = rule.confidence,
                                 lift = rule.lift) for rule in rules],
        transactions = len(request_body.transactions)
    )
