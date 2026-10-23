'''
    Prediction Schemas (Request/Response)
'''
from enum import Enum

from pydantic import BaseModel, Field

from schemas.base import NumPyValidatorBase

class ComputeCostLinearRequest(NumPyValidatorBase):
    '''
        Request model for calculating linear regression cost.
    '''
    x: list[float] | list[list[float]] = Field(
        ...,
        description = 'Feature vector/matrix X for linear regression cost calculation.'
    )
    y: list[float] = Field(
        ...,
        description = 'Target vector y for linear regression cost calculation.'
    )
    w: float | list[float] = Field(
        ...,
        description = 'Weight parameter(s) w for linear regression cost calculation.'
    )
    b: float = Field(
        ...,
        description = 'Bias parameter b for linear regression cost calculation.'
    )

    model_config = {
        'json_schema_extra': {
            'examples': [
                {
                    'x': [1.0, 2.0, 3.0],
                    'y': [2.0, 4.0, 6.0],
                    'w': 2.0,
                    'b': 0.0
                },
                {
                    'x': [[1.0, 2.0], [3.0, 4.0]],
                    'y': [5.0, 7.0],
                    'w': [1.0, 1.0],
                    'b': 1.0
                }
            ]
        }
    }

class ComputeCostLinearResponse(BaseModel):
    '''
        Response model for linear regression cost.
    '''
    cost: float = Field(
        ...,
        description = 'Calculated cost for the linear regression model.'
    )

class ComputeGradientLinearRequest(NumPyValidatorBase):
    '''
        Request model for calculating linear regression gradient.
    '''
    x: list[float] | list[list[float]] = Field(
        ...,
        description = 'Feature vector/matrix X for linear regression gradient calculation.'
    )
    y: list[float] = Field(
        ...,
        description = 'Target vector y for linear regression gradient calculation.'
    )
    w: float | list[float] = Field(
        ...,
        description = 'Weight parameter(s) w for linear regression gradient calculation.'
    )
    b: float = Field(
        ...,
        description = 'Bias parameter b for linear regression gradient calculation.'
    )

    model_config = {
        'json_schema_extra': {
            'examples': [
                {
                    'x': [1.0, 2.0, 3.0],
                    'y': [2.0, 4.0, 6.0],
                    'w': 1.0,
                    'b': 0.0
                },
                {
                    'x': [[1.0, 2.0], [3.0, 4.0]],
                    'y': [5.0, 7.0],
                    'w': [1.0, 1.0],
                    'b': 1.0
                }
            ]
        }
    }

class ComputeGradientLinearResponse(BaseModel):
    '''
        Response model for linear regression gradient.
    '''
    dj_db: float = Field(
        ...,
        description = 'Gradient of cost with respect to bias (b).'
    )
    dj_dw: float | list[float] = Field(
        ...,
        description = 'Gradient of cost with respect to weight(s) (w).'
    )

class TrainLinearRegressionRequest(NumPyValidatorBase):
    '''
        Request model for performing linear regression training (gradient descent).
    '''
    x: list[float] | list[list[float]] = Field(
        ...,
        description = 'Feature vector/matrix X for linear regression training.'
    )
    y: list[float] = Field(
        ...,
        description = 'Target vector y for linear regression training.'
    )
    w_in: float | list[float] = Field(
        ...,
        description = 'Initial weight parameter(s) w for linear regression.'
    )
    b_in: float = Field(
        ...,
        description = 'Initial bias parameter b for linear regression.'
    )
    alpha: float = Field(
        ...,
        description = 'Learning rate (alpha) for linear regression training.'
    )
    num_iters: int = Field(
        ...,
        description = 'Number of iterations for linear regression training.'
    )

    model_config = {
        'json_schema_extra': {
            'examples': [
                {
                    'x': [1.0, 2.0, 3.0, 4.0],
                    'y': [3.0, 5.0, 7.0, 9.0],
                    'w_in': 0.0,
                    'b_in': 0.0,
                    'alpha': 0.01,
                    'num_iters': 1000
                },
                {
                    'x': [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]],
                    'y': [3.0, 7.0, 11.0],
                    'w_in': [0.0, 0.0],
                    'b_in': 0.0,
                    'alpha': 0.01,
                    'num_iters': 1000
                }
            ]
        }
    }

class TrainLinearRegressionResponse(BaseModel):
    '''
        Response model for linear regression training results.
    '''
    w_final: float | list[float] = Field(
        ...,
        description = 'Final weight parameter(s) w after training.'
    )
    b_final: float = Field(
        ...,
        description = 'Final bias parameter b after training.'
    )
    J_history: list[float] = Field(
        ...,
        description = 'History of cost function J during training.'
    )
    p_history: list[list[float | list[float]]] = Field(
        ...,
        description = 'History of [w_epoch, b_epoch] during training.'
    )
    num_iters: int = Field(
        ...,
        description = 'The number of iterations used for training.'
    )

class PredictLinearRequest(NumPyValidatorBase):
    '''
        Request model for linear regression prediction.
    '''
    x_test: list[float] | list[list[float]] = Field(
        ...,
        description = 'Test feature vector/matrix X for prediction.'
    )
    w: float | list[float] = Field(
        ...,
        description = 'Weight parameter(s) w (from trained model).'
    )
    b: float = Field(
        ...,
        description = 'Bias parameter b (from trained model).'
    )

    model_config = {
        'json_schema_extra': {
            'examples': [
                {
                    'x_test': [7.0, 8.0],
                    'w': 2.0,
                    'b': 1.0
                },
                {
                    'x_test': [[7.0, 8.0], [9.0, 10.0]],
                    'w': [1.0, 2.0],
                    'b': 0.0
                }
            ]
        }
    }

class PredictLinearResponse(BaseModel):
    '''
        Response model for linear regression prediction.
    '''
    predictions: list[float] = Field(
        ...,
        description = 'List of predicted numerical values for new inputs.'
    )


class ForecastModel(str, Enum):
    '''
        The projection models the service chooses among.
    '''
    NAIVE = 'NAIVE'
    DAMPED_TREND = 'DAMPED_TREND'
    HOLT_WINTERS = 'HOLT_WINTERS'
    LINEAR = 'LINEAR'
    MOVING_AVERAGE = 'MOVING_AVERAGE'
    MEAN = 'MEAN'
    DRIFT = 'DRIFT'
    SIMPLE_EXPONENTIAL = 'SIMPLE_EXPONENTIAL'
    HOLT = 'HOLT'
    THETA = 'THETA'


class ForecastRequest(BaseModel):
    '''
        A series to project. The caller sends the series and what it is; the
        parameters of each model are fitted by the service, from the series
        itself (Rafael, 19-oct-2026). It may also name the models: one is used
        as asked, several compete (23-oct-2026).
    '''
    values: list[float] = Field(..., min_length = 2, max_length = 1000,
                                description = 'The history, oldest first.')
    horizon: int = Field(..., ge = 1, le = 120, description = 'Steps ahead.')
    season_length: int | None = Field(
        None, ge = 2, le = 366,
        description = 'Points per season (12 for months); None when the series has none.')
    backtest_points: int = Field(..., ge = 1, le = 120,
                                 description = 'Last points the models are measured on.')
    models: list[ForecastModel] | None = Field(
        None, min_length = 1,
        description = 'The models to compare; one model is used as asked. None: the '
                      'service chooses among the damped trend and Holt-Winters.')
    window: int | None = Field(
        None, ge = 1, le = 120,
        description = 'Points the moving average takes; all of them when not given.')


class ForecastResponse(BaseModel):
    '''
        The projection, the model it came from and how good that model has
        been on the series itself, next to the naive guess.
    '''
    model: ForecastModel
    forecast: list[float]
    error_percent: float | None = Field(
        None, description = 'Mean absolute % error on the tested points; None without data.')
    naive_error_percent: float | None = Field(
        None, description = 'The same error for "the next value is the same as the last".')
    tested_points: int = Field(
        ..., ge = 0, description = 'How many points the models were measured on.')


class CompareRequest(BaseModel):
    '''
        Several models measured on the same series (23-oct-2026, from the bench
        QUOTES kept): each projects `horizon` steps from every point that
        leaves `min_train` behind it, and the misses are averaged.
    '''
    values: list[float] = Field(..., min_length = 2, max_length = 5000,
                                description = 'The history, oldest first.')
    horizon: int = Field(..., ge = 1, le = 366, description = 'Steps ahead.')
    models: list[ForecastModel] = Field(..., min_length = 1, description = 'Models to run.')
    min_train: int = Field(..., ge = 2, description = 'Points a replay needs before it projects.')
    min_windows: int = Field(..., ge = 1, description = 'Replays an error needs to be published.')
    window: int | None = Field(None, ge = 1, le = 366,
                               description = 'Points the moving average takes.')


class ModelRun(BaseModel):
    '''
        One model on the series: its projection and how far it missed.
    '''
    model: ForecastModel
    forecast: list[float]
    mean_absolute_error: float | None = Field(
        None, description = 'Mean absolute miss over the replays, in the unit of the series; '
                            'None with too few replays.')


class CompareResponse(BaseModel):
    '''
        Every model asked for, the one that missed least first, and the naive
        guess measured the same way.
    '''
    runs: list[ModelRun]
    naive_mean_absolute_error: float | None = None
    windows: int = Field(..., ge = 0, description = 'How many replays were averaged.')
