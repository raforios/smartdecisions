'''
    Classification Schemas (Request/Response)
'''
from typing import Union, List
from pydantic import BaseModel, Field

from schemas.base import NumPyValidatorBase

class SigmoidBatchRequest(BaseModel): # pylint: disable=too-few-public-methods
    '''
        Request model for calculating sigmoid on a batch of values.
    '''
    z_values: List[Union[float, int]] = Field(
        ...,
        description = 'List of input values (z) for sigmoid calculation.'
    )

    model_config = {
        'json_schema_extra': {
            'examples': [
                {
                    'z_values': [0.0, 1.0, -1.0, 5.0, -5.0]
                }
            ]
        }
    }

class ComputeCostLogisticRequest(NumPyValidatorBase):
    '''
        Request model for calculating logistic regression cost.
    '''
    x_matrix: List[List[float]] = Field(
        ...,
        description = 'Feature matrix X for logistic regression cost calculation.'
    )
    y: List[float] = Field(
        ...,
        description = 'Target vector y for logistic regression cost calculation.'
    )
    w: List[float] = Field(
        ...,
        description = 'Weight parameters w for logistic regression cost calculation.'
    )
    b: float = Field(
        ...,
        description = 'Bias parameter b for logistic regression cost calculation.'
    )

    model_config = {
        'json_schema_extra': {
            'examples': [
                {
                    'x_matrix': [[1.0, 2.0], [1.0, 3.0]],
                    'y': [0.0, 1.0],
                    'w': [0.1, 0.2],
                    'b': -0.5
                }
            ]
        }
    }

class ComputeGradientLogisticRequest(NumPyValidatorBase):
    '''
        Request model for calculating logistic regression gradient.
    '''
    x_matrix: List[List[float]] = Field(
        ...,
        description = 'Feature matrix X for logistic regression gradient calculation.'
    )
    y: List[float] = Field(
        ...,
        description = 'Target vector y for logistic regression gradient calculation.'
    )
    w: List[float] = Field(
        ...,
        description = 'Weight parameters w for logistic regression gradient calculation.'
    )
    b: float = Field(
        ...,
        description = 'Bias parameter b for logistic regression gradient calculation.'
    )

    model_config = {
        'json_schema_extra': {
            'examples': [
                {
                    'x_matrix': [[1.0, 2.0], [1.0, 3.0]],
                    'y': [0.0, 1.0],
                    'w': [0.1, 0.2],
                    'b': -0.5
                }
            ]
        }
    }

class ComputeGradientLogisticResponse(BaseModel):
    '''
        Response model for logistic regression gradient.
    '''
    dj_db: float = Field(
        ...,
        description = 'Gradient of cost with respect to bias (b) for logistic regression.'
    )
    dj_dw: List[float] = Field(
        ...,
        description = 'Gradient of cost with respect to weights (w) for logistic regression.'
    )

    model_config = {
        'json_schema_extra': {
            'examples': [
                {
                    'dj_db': 0.05,
                    'dj_dw': [0.1, 0.2]
                }
            ]
        }
    }

class GradientDescentLogisticRequest(NumPyValidatorBase):
    '''
        Request model for performing logistic regression gradient descent.
    '''
    x_matrix: List[List[float]] = Field(
        ...,
        description = 'Feature matrix X for logistic regression gradient descent.'
    )
    y: List[float] = Field(
        ...,
        description = 'Target vector y for logistic regression gradient descent.'
    )
    w_in: List[float] = Field(
        ...,
        description = 'Initial weight parameters w for logistic regression.'
    )
    b_in: float = Field(
        ...,
        description = 'Initial bias parameter b for logistic regression.'
    )
    alpha: float = Field(
        ...,
        description = 'Learning rate (alpha) for logistic regression gradient descent.'
    )
    num_iters: int = Field(
        ...,
        description = 'Number of iterations for logistic regression gradient descent.'
    )

    model_config = {
        'json_schema_extra': {
            'examples': [
                {
                    'x_matrix': [[1.0, 2.0], [1.0, 3.0], [1.0, 4.0]],
                    'y': [0.0, 1.0, 1.0],
                    'w_in': [0.0, 0.0],
                    'b_in': 0.0,
                    'alpha': 0.01,
                    'num_iters': 1000
                }
            ]
        }
    }

class GradientDescentLogisticResponse(BaseModel):
    '''
        Response model for logistic regression gradient descent results.
    '''
    w: List[float] = Field(
        ...,
        description = 'Final weight parameters w after logistic regression training.'
    )
    b: float = Field(
        ...,
        description = 'Final bias parameter b after logistic regression training.'
    )
    J_history: List[float] = Field(
        ...,
        description = 'History of cost function J during logistic regression training.'
    )
    p_history: List[List[Union[List[float], float]]] = Field(
        ...,
        description = 'History of [w_epoch, b_epoch] during logistic regression training.'
    )

    model_config = {
        'json_schema_extra': {
            'examples': [
                {
                    'w': [0.15, 0.25],
                    'b': -0.75,
                    'J_history': [0.6, 0.55, 0.5, 0.48],
                    'p_history': [[[0.0, 0.0], 0.0], [[0.05, 0.1], -0.1], [[0.1, 0.2], -0.5]]
                }
            ]
        }
    }

class PredictLogisticRequest(NumPyValidatorBase):
    '''
        Request model for logistic regression prediction.
    '''
    x_matrix: List[List[float]] = Field(
        ...,
        description = 'Feature matrix X for logistic regression prediction.'
    )
    w: List[float] = Field(
        ...,
        description = 'Weight parameters w (from trained logistic model).'
    )
    b: float = Field(
        ...,
        description = 'Bias parameter b (from trained logistic model).'
    )

    model_config = {
        'json_schema_extra': {
            'examples': [
                {
                    'x_matrix': [[0.5, 1.2], [-0.1, 0.8]],
                    'w': [0.07, 0.06],
                    'b': -8.06
                }
            ]
        }
    }

class PredictLogisticResponse(BaseModel):
    '''
        Response model for logistic regression prediction.
    '''
    predictions: List[int] = Field(
        ...,
        description = 'List of predicted labels (0 or 1) from logistic regression.'
    )

    model_config = {
        'json_schema_extra': {
            'examples': [
                {
                    'predictions': [0, 1]
                }
            ]
        }
    }
