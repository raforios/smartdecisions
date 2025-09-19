'''
    Normalized Schemas (Request/Response)
'''
from typing import List
from pydantic import BaseModel, Field

from schemas.base import NumPyValidatorBase

class NormalizeFeaturesRequest(NumPyValidatorBase):
    '''
        Request model for feature normalization (z-score).
    '''
    x_matrix: List[List[float]] = Field(
        ...,
        description = 'Feature matrix X to normalize using Z-score.'
    )

    model_config = {
        'json_schema_extra': {
            'examples': [
                {
                    'x_matrix': [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]
                }
            ]
        }
    }

class NormalizeFeaturesResponse(BaseModel):
    '''
        Response model for feature normalization (z-score).
    '''
    x_norm: List[List[float]] = Field(
        ...,
        description = 'Column-normalized feature matrix X using Z-score.'
    )
    mu: List[float] = Field(
        ...,
        description = 'Average (mean) of each feature (column) used for normalization.'
    )
    sigma: List[float] = Field(
        ...,
        description = 'Standard deviation of each feature (column) used for normalization.'
    )

    model_config = {
        'json_schema_extra': {
            'examples': [
                {
                    'x_norm': [[-1.22, -1.22], [0.0, 0.0], [1.22, 1.22]],
                    'mu': [3.0, 4.0],
                    'sigma': [1.63, 1.63]
                }
            ]
        }
    }
