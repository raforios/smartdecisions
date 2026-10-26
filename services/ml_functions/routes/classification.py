'''
    Classification: routes handler
'''
from typing import Any

from fastapi import APIRouter, Depends
from services.security import get_current_user
from services.logger_config import custom_logger as logger
from controllers.classification import (
    calculating_sigmoid,
    calculating_cost_logistic,
    calculating_gradient_logistic,
    performing_gradient_descent_logistic,
    predicting_logistic_classification,
    ranking_tiers,
    mining_association_rules
)
from schemas.classification import (
    AssociationRulesRequest,
    AssociationRulesResponse,
    TiersRequest,
    TiersResponse,
    SigmoidBatchRequest,
    ComputeCostLogisticRequest,
    ComputeGradientLogisticRequest,
    ComputeGradientLogisticResponse,
    GradientDescentLogisticRequest,
    PredictLogisticRequest,
    PredictLogisticResponse
)

router = APIRouter(prefix = '/v1/classification', tags = ['ML Classification'])

@router.post(
    '/sigmoid-batch',
    summary = 'Calculate sigmoid function for a batch of values',
    description = '''Calculates the sigmoid function for each value in a batch
        and returns the results. This is useful for testing the sigmoid service.'''
)
async def sigmoid_batch_algorithm(
    request: SigmoidBatchRequest,
    current_user: str = Depends(get_current_user)
) -> list[float]:
    '''
    Calculates the sigmoid function for each value in a list of `z_values`.

    Args:
        request (SigmoidBatchRequest): A Pydantic model containing
                                        a list of `z_values`.
        current_user (str): The authenticated user's identifier
                            (dependency-injected).

    Returns:
        float | numpy.ndarray: The result of the sigmoid calculation.
                                     Returns a float if a single value was passed,
                                     or a NumPy array if a list was passed.

    Raises:
        UnauthorizedError: If authentication fails.
        ServiceUnavailableError: If an internal server error occurs during calculation.
    '''
    message = f'User: {current_user} requested sigmoid for batch z_values: {request.z_values}'
    logger.info(message)
    return await calculating_sigmoid(request)

@router.post(
    '/cost-logistic',
    summary = 'Compute logistic regression cost',
    description = '''Calculates the cost (J) for a given logistic regression
        model (x, y, w, b).'''
)
async def compute_cost_logistic_route(
    request: ComputeCostLogisticRequest,
    current_user: str = Depends(get_current_user)
) -> float:
    '''
    Calculates the cost for logistic regression based on provided data, weights, and bias.

    This endpoint takes the feature matrix X, target array y, weight parameters w,
    and bias b in the request body, and returns the computed logistic regression cost.
    Authentication is required.

    Args:
        request (ComputeCostLogisticRequest): A Pydantic model containing
                                                      x_matrix, y, w, and b.
        current_user (str): The authenticated user's identifier
                            (dependency-injected).

    Returns:
        float: The calculated logistic regression cost.

    Raises:
        UnauthorizedError: If authentication fails.
        ServiceUnavailableError: If an internal server error occurs during calculation.
    '''
    message = f'User: {current_user} requested logistic regression cost calculation.'
    logger.info(message)
    return await calculating_cost_logistic(request)

@router.post(
    '/gradient-logistic',
    response_model = ComputeGradientLogisticResponse,
    summary = 'Compute logistic regression gradient',
    description = '''Calculates the gradients (dj_dw, dj_db) for a given logistic
        regression model (x, y, w, b).'''
)
async def compute_gradient_logistic_route(
    request: ComputeGradientLogisticRequest,
    current_user: str = Depends(get_current_user)
) -> dict[str, Any]:
    '''
    Calculates the gradient for logistic regression based on provided data, weights, and bias.

    This endpoint takes the feature matrix X, target array y, weight parameters w,
    and bias b in the request body, and returns the computed logistic regression
    gradient (dj_db, dj_dw). Authentication is required.

    Args:
        request (ComputeGradientLogisticRequest): A Pydantic model containing
                                                          x_matrix, y, w, and b.
        current_user (str): The authenticated user's identifier
                            (dependency-injected).

    Returns:
        ComputeGradientLogisticResponse: An object containing dj_db (float)
                                                 and dj_dw (list of floats).

    Raises:
        UnauthorizedError: If authentication fails.
        ServiceUnavailableError: If an internal server error occurs during calculation.
    '''
    message = f'User: {current_user} requested logistic regression gradient calculation.'
    logger.info(message)
    return await calculating_gradient_logistic(request)

@router.post(
    '/train-logistic-regression',
    summary = 'Train logistic regression model using gradient descent',
    description = '''Performs batch gradient descent to train a logistic regression
        model and returns the final parameters (w, b) and training history.'''
)
async def train_logistic_regression_route(
    request: GradientDescentLogisticRequest,
    current_user: str = Depends(get_current_user)
) -> dict[str, Any]:
    '''
    Performs logistic regression gradient descent to find optimal parameters (w, b).

    This endpoint takes the feature matrix X, target array y, initial weights w_in,
    initial bias b_in, learning rate alpha, and number of iterations num_iters
    in the request body. It returns the final weights and bias, and their history.
    Authentication is required.

    Args:
        request (GradientDescentLogisticRequest): A Pydantic model containing
                                                  x_matrix, y, initial w, initial b,
                                                  alpha, and num_iters.
        current_user (str): The authenticated user's identifier
                            (dependency-injected).

    Returns:
        dict: A dictionary containing the final w, b, and the history of cost
              and parameters.

    Raises:
        UnauthorizedError: If authentication fails.
        ServiceUnavailableError: If an internal server error occurs during calculation.
    '''
    message = f'User: {current_user} requested logistic regression training using gradient descent.'
    logger.info(message)
    return await performing_gradient_descent_logistic(request)

@router.post(
    '/predict-logistic-classification',
    response_model = PredictLogisticResponse,
    summary = 'Make predictions using a trained logistic regression model',
    description = '''Uses a trained logistic regression model (w, b) to predict
        output for new input features (x_test).'''
)
async def predict_logistic_classification_route(
    request: PredictLogisticRequest,
    current_user: str = Depends(get_current_user)
) -> PredictLogisticResponse:
    '''
    Predicts values using learned logistic regression parameters (w, b) and new data.

    This endpoint takes a feature matrix X_test, learned weight parameters w,
    and bias b in the request body, and returns a list of predicted labels (0 or 1).
    Authentication is required.

    Args:
        request (PredictLogisticRequest): A Pydantic model containing
                                                  x_test, w, and b for prediction.
        current_user (str): The authenticated user's identifier
                            (dependency-injected).

    Returns:
        PredictLogisticResponse: An object containing the list of predicted labels.

    Raises:
        UnauthorizedError: If authentication fails.
        ServiceUnavailableError: If an internal server error occurs during calculation.
    '''
    message = f'User: {current_user} requested logistic regression prediction for new data.'
    logger.info(message)
    return await predicting_logistic_classification(request)


@router.post(
    '/tiers',
    response_model = TiersResponse,
    summary = 'Split values in tiers by their place in the ranking',
    description = '''Sorts the values from the highest down and gives each one the
        tier of the share of the ranking it falls in: with cuts [0.2, 0.5] the top
        20 % is tier 0, the next 30 % tier 1 and the rest tier 2. The client value
        segmentation COMMERCIAL shows, and colours its route stops with.'''
)
async def tiers_route(
    request: TiersRequest,
    current_user: str = Depends(get_current_user)
) -> TiersResponse:
    '''
        Splits the values in tiers by their place in the ranking.

        Args:
            request (TiersRequest): The values and the cuts.
            current_user (str): The authenticated user's identifier (dependency-injected).

        Returns:
            TiersResponse: The tier of each value.
    '''
    message = (f'User: {current_user} asked tiers of {len(request.values)} value(s) '
               f'with cuts {request.cuts}.')
    logger.info(message)
    return await ranking_tiers(request)


@router.post(
    '/association-rules',
    response_model = AssociationRulesResponse,
    summary = 'Mine association rules (Apriori)',
    description = '''Finds the itemsets present in at least `min_support` of the
        transactions and derives every rule antecedents -> consequents whose lift
        reaches `min_lift`, with support, confidence and lift. The affinity
        COMMERCIAL recommends products with.'''
)
async def association_rules_route(
    request: AssociationRulesRequest,
    current_user: str = Depends(get_current_user)
) -> AssociationRulesResponse:
    '''
        Mines the association rules of the transactions.

        Args:
            request (AssociationRulesRequest): The transactions and the thresholds.
            current_user (str): The authenticated user's identifier (dependency-injected).

        Returns:
            AssociationRulesResponse: The rules kept.
    '''
    message = (f'User: {current_user} asked association rules over '
               f'{len(request.transactions)} transaction(s).')
    logger.info(message)
    return await mining_association_rules(request)
