'''
    Prediction controller
'''

from services import training
from services.forecast import DEFAULT_MODELS, ForecastSpec, choose_and_project
from services.forecast_bench import BenchSpec, compare, replays
from services.utils import handle_operation
from schemas.prediction import (
    ComputeCostLinearRequest,
    ComputeCostLinearResponse,
    ComputeGradientLinearRequest,
    ComputeGradientLinearResponse,
    TrainLinearRegressionRequest,
    TrainLinearRegressionResponse,
    PredictLinearRequest,
    PredictLinearResponse,
    CompareRequest,
    CompareResponse,
    ForecastRequest,
    ForecastResponse,
    ModelRun
)

@handle_operation(exc_type = (ValueError, TypeError))
async def compute_cost_linear_regression(
    request_body: ComputeCostLinearRequest
) -> ComputeCostLinearResponse:
    '''
        The cost of a linear model.
    '''
    return training.linear_cost(request_body)


@handle_operation(exc_type = (ValueError, TypeError))
async def compute_gradient_linear_regression(
    request_body: ComputeGradientLinearRequest
) -> ComputeGradientLinearResponse:
    '''
        The gradient of the cost of a linear model.
    '''
    return training.linear_gradient(request_body)


@handle_operation(exc_type = (ValueError, TypeError))
async def train_linear_regression(
    request_body: TrainLinearRegressionRequest
) -> TrainLinearRegressionResponse:
    '''
        Fits a linear model by gradient descent.
    '''
    return training.train_linear(request_body)


@handle_operation(exc_type = (ValueError, TypeError))
async def predict_linear_regression(
    request_body: PredictLinearRequest
) -> PredictLinearResponse:
    '''
        The predictions of a trained linear model.
    '''
    return training.predict_linear(request_body)


@handle_operation(exc_type = (ValueError, TypeError))
async def forecast_series(request_body: ForecastRequest) -> ForecastResponse:
    '''
    Controller to project a series with the model that best follows it.
    '''
    spec = ForecastSpec(
        horizon = request_body.horizon,
        season = request_body.season_length,
        points = request_body.backtest_points,
        models = (tuple(model.value for model in request_body.models)
                  if request_body.models else DEFAULT_MODELS),
        window = request_body.window
    )
    projection = choose_and_project(request_body.values, spec)
    return ForecastResponse(
        model = projection.model,
        forecast = projection.forecast,
        error_percent = projection.error_percent,
        naive_error_percent = projection.naive_error_percent,
        tested_points = projection.tested_points
    )


@handle_operation(exc_type = (ValueError, TypeError))
async def compare_models(request_body: CompareRequest) -> CompareResponse:
    '''
    Controller running several models over a series, each measured on its replays.
    '''
    spec = BenchSpec(horizon = request_body.horizon, min_train = request_body.min_train,
                     min_windows = request_body.min_windows, window = request_body.window)
    runs, naive_error = compare(request_body.values,
                                [model.value for model in request_body.models], spec)
    return CompareResponse(
        runs = [ModelRun(model = run.model, forecast = run.forecast,
                         mean_absolute_error = run.mean_absolute_error) for run in runs],
        naive_mean_absolute_error = naive_error,
        windows = replays(request_body.values, spec)
    )
