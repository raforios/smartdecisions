'''
    Prediction Schemas (Request/Response)
'''
from typing import Union, List
from pydantic import BaseModel, Field

class ComputeCostLinearRequest(BaseModel):
    '''
        Request model for calculating linear regression cost.
    '''
    x: Union[List[float], List[List[float]]] = Field(
        ...,
        description = 'Feature vector/matrix X for linear regression cost calculation.'
    )
    y: List[float] = Field(
        ...,
        description = 'Target vector y for linear regression cost calculation.'
    )
    w: Union[float, List[float]] = Field(
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

class ComputeGradientLinearRequest(BaseModel):
    '''
        Request model for calculating linear regression gradient.
    '''
    x: Union[List[float], List[List[float]]] = Field(
        ...,
        description = 'Feature vector/matrix X for linear regression gradient calculation.'
    )
    y: List[float] = Field(
        ...,
        description = 'Target vector y for linear regression gradient calculation.'
    )
    w: Union[float, List[float]] = Field(
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
    dj_dw: Union[float, List[float]] = Field(
        ...,
        description = 'Gradient of cost with respect to weight(s) (w).'
    )

class TrainLinearRegressionRequest(BaseModel):
    '''
        Request model for performing linear regression training (gradient descent).
    '''
    x: Union[List[float], List[List[float]]] = Field(
        ...,
        description = 'Feature vector/matrix X for linear regression training.'
    )
    y: List[float] = Field(
        ...,
        description = 'Target vector y for linear regression training.'
    )
    w_in: Union[float, List[float]] = Field(
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
    w_final: Union[float, List[float]] = Field(
        ...,
        description = 'Final weight parameter(s) w after training.'
    )
    b_final: float = Field(
        ...,
        description = 'Final bias parameter b after training.'
    )
    J_history: List[float] = Field(
        ...,
        description = 'History of cost function J during training.'
    )
    p_history: List[List[Union[float, List[float]]]] = Field(
        ...,
        description = 'History of [w_epoch, b_epoch] during training.'
    )
    num_iters: int = Field(
        ...,
        description = 'The number of iterations used for training.'
    )

class PredictLinearRequest(BaseModel):
    '''
        Request model for linear regression prediction.
    '''
    x_test: Union[List[float], List[List[float]]] = Field(
        ...,
        description = 'Test feature vector/matrix X for prediction.'
    )
    w: Union[float, List[float]] = Field(
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
    predictions: List[float] = Field(
        ...,
        description = 'List of predicted numerical values for new inputs.'
    )
