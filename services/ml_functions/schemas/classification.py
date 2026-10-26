'''
    Classification Schemas (Request/Response)
'''
from pydantic import BaseModel, Field, field_validator

from schemas.base import NumPyValidatorBase

class SigmoidBatchRequest(BaseModel): # pylint: disable=too-few-public-methods
    '''
        Request model for calculating sigmoid on a batch of values.
    '''
    z_values: list[float | int] = Field(
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
    x_matrix: list[list[float]] = Field(
        ...,
        description = 'Feature matrix X for logistic regression cost calculation.'
    )
    y: list[float] = Field(
        ...,
        description = 'Target vector y for logistic regression cost calculation.'
    )
    w: list[float] = Field(
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
    x_matrix: list[list[float]] = Field(
        ...,
        description = 'Feature matrix X for logistic regression gradient calculation.'
    )
    y: list[float] = Field(
        ...,
        description = 'Target vector y for logistic regression gradient calculation.'
    )
    w: list[float] = Field(
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
    dj_dw: list[float] = Field(
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
    x_matrix: list[list[float]] = Field(
        ...,
        description = 'Feature matrix X for logistic regression gradient descent.'
    )
    y: list[float] = Field(
        ...,
        description = 'Target vector y for logistic regression gradient descent.'
    )
    w_in: list[float] = Field(
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
    w: list[float] = Field(
        ...,
        description = 'Final weight parameters w after logistic regression training.'
    )
    b: float = Field(
        ...,
        description = 'Final bias parameter b after logistic regression training.'
    )
    J_history: list[float] = Field(
        ...,
        description = 'History of cost function J during logistic regression training.'
    )
    p_history: list[list[list[float] | float]] = Field(
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
    x_matrix: list[list[float]] = Field(
        ...,
        description = 'Feature matrix X for logistic regression prediction.'
    )
    w: list[float] = Field(
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
    predictions: list[int] = Field(
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


class TiersRequest(BaseModel):
    '''
        Values to split in tiers by their place in the ranking (24-oct-2026,
        from the segmentation COMMERCIAL kept).
    '''
    values: list[float] = Field(..., min_length = 1, max_length = 100000,
                                description = 'One value per member, in any order.')
    cuts: list[float] = Field(
        ..., min_length = 1, max_length = 10,
        description = 'Increasing shares of the ranking (0..1) where each tier ends.')

    @field_validator('cuts')
    @classmethod
    def _increasing_shares(
        cls,
        cuts: list[float]
    ) -> list[float]:
        '''
            The cuts are shares, strictly increasing.
        '''
        if any(cut <= 0 or cut >= 1 for cut in cuts) or cuts != sorted(set(cuts)):
            raise ValueError('cuts must be strictly increasing shares between 0 and 1')
        return cuts


class TiersResponse(BaseModel):
    '''
        The tier of each value, in the order they came (0 = the top).
    '''
    tiers: list[int]


class AssociationRulesRequest(BaseModel):
    '''
        Transactions to mine for association rules (24-oct-2026, from the
        Apriori COMMERCIAL kept).
    '''
    transactions: list[list[str]] = Field(
        ..., max_length = 200000, description = 'The items of each transaction.')
    min_support: float = Field(..., gt = 0, le = 1,
                               description = 'Minimum share of transactions.')
    min_lift: float = Field(..., ge = 0, description = 'Minimum lift a rule needs.')


class AssociationRule(BaseModel):
    '''
        When a transaction holds `antecedents`, it tends to hold `consequents` too.
    '''
    antecedents: list[str]
    consequents: list[str]
    support: float
    confidence: float
    lift: float


class AssociationRulesResponse(BaseModel):
    '''
        The rules kept and how many transactions were mined.
    '''
    rules: list[AssociationRule]
    transactions: int = Field(..., ge = 0)
