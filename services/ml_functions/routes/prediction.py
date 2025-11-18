'''
    Prediction: routes handler
'''
from fastapi import APIRouter, Depends
from services.security import get_current_user
from services.logger_config import custom_logger as logger
from controllers.prediction import (
    compute_cost_linear_regression,
    compute_gradient_linear_regression,
    train_linear_regression,
    predict_linear_regression
)
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

router = APIRouter(prefix = '/v1/prediction', tags = ['ML Prediction'])

@router.post(
    '/compute-cost',
    response_model = ComputeCostLinearResponse,
    summary = 'Compute linear regression cost',
    description = '''Calculates the cost (J) for a given linear regression
        model (x, y, w, b).'''
)
async def compute_cost_linear_regression_route(
    request: ComputeCostLinearRequest,
    current_user: str = Depends(get_current_user)
):
    '''
        Calculates the cost for linear regression based on provided data, weights, and bias.

        This endpoint takes the feature matrix X, target array y, weight parameters w,
        and bias b in the request body, and returns the computed linear regression cost.
        Authentication is required.

        Args:
            request (ComputeCostLinearRequest): A Pydantic model containing
                                                        x_matrix, y, w, and b.
            current_user (str): The authenticated user's identifier
                                (dependency-injected).

        Returns:
            ComputeCostLinearResponse: An object containing the calculated
                                                linear regression cost as a float.

        Raises:
            UnauthorizedError: If authentication fails.
            ServiceUnavailableError: If an internal server error occurs during calculation.
    '''
    message = f'User: {current_user} requested linear regression cost calculation.'
    logger.info(message)
    return await compute_cost_linear_regression(request)

@router.post(
    '/compute-gradient',
    response_model = ComputeGradientLinearResponse,
    summary = 'Compute linear regression gradient',
    description = '''Calculates the gradients (dj_dw, dj_db) for a given linear
        regression model (x, y, w, b).'''
)
async def compute_gradient_linear_regression_route(
    request: ComputeGradientLinearRequest,
    current_user: str = Depends(get_current_user)
):
    '''
        Calculates the gradient for linear regression based on provided data, weights, and bias.

        This endpoint takes the feature matrix X, target array y, weight parameters w,
        and bias b in the request body, and returns the computed linear regression
        gradient (dj_db, dj_dw). Authentication is required.

        Args:
            request (ComputeGradientLinearRequest): A Pydantic model containing
                                                            x_matrix, y, w, and b.
            current_user (str): The authenticated user's identifier
                                (dependency-injected).

        Returns:
            ComputeGradientLinearResponse: An object containing dj_db (float)
                                                    and dj_dw (list of floats).

        Raises:
            UnauthorizedError: If authentication fails.
            ServiceUnavailableError: If an internal server error occurs during calculation.
    '''
    message = f'User: {current_user} requested linear regression gradient calculation.'
    logger.info(message)
    return await compute_gradient_linear_regression(request)

@router.post(
    '/train-linear-regression',
    response_model = TrainLinearRegressionResponse,
    summary = 'Train linear regression model using gradient descent',
    description = '''Performs batch gradient descent to train a linear regression
        model and returns the final parameters (w, b) and training history.'''
)
async def train_linear_regression_route(
    request: TrainLinearRegressionRequest,
    current_user: str = Depends(get_current_user)
):
    '''
        Performs linear regression gradient descent to find optimal parameters (w, b).

        This endpoint takes the feature matrix X, target array y, initial weights w_in,
        initial bias b_in, learning rate alpha, and number of iterations num_iters
        in the request body. It returns the final weights and bias, and their history.
        Authentication is required.

        Args:
            request (TrainLinearRegressionRequest): A Pydantic model containing
                                                    x_matrix, y, initial w, initial b,
                                                    alpha, and num_iters.
            current_user (str): The authenticated user's identifier
                                (dependency-injected).

        Returns:
            TrainLinearRegressionResponse: An object containing the final w, b,
                                        and the history of cost and parameters.

        Raises:
            UnauthorizedError: If authentication fails.
            ServiceUnavailableError: If an internal server error occurs during calculation.
    '''
    message = f'User: {current_user} requested linear regression training using gradient descent.'
    logger.info(message)
    return await train_linear_regression(request)

@router.post(
    '/predict-linear-regression',
    response_model = PredictLinearResponse,
    summary = 'Make predictions using a trained linear regression model',
    description = '''Uses a trained linear regression model (w, b) to predict
        output for new input features (x_test).'''
)
async def predict_linear_regression_route(
    request: PredictLinearRequest,
    current_user: str = Depends(get_current_user)
):
    '''
        Predicts values using learned linear regression parameters (w, b) and new data.

        This endpoint takes a feature matrix X_test, learned weight parameters w,
        and bias b in the request body, and returns a list of predicted values.
        Authentication is required.

        Args:
            request (PredictLinearRequest): A Pydantic model containing
                                                    x_test, w, and b for prediction.
            current_user (str): The authenticated user's identifier
                                (dependency-injected).

        Returns:
            PredictLinearResponse: An object containing the list of predicted values.

        Raises:
            UnauthorizedError: If authentication fails.
            ServiceUnavailableError: If an internal server error occurs during calculation.
    '''
    message = f'User: {current_user} requested linear regression prediction for new data.'
    logger.info(message)
    return await predict_linear_regression(request)
