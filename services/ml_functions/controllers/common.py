'''
    Common controller for ML operations
'''
import numpy as np
from services.logger_config import custom_logger as logger
from services.utils import handle_operation
from services.machine_learning import (
    zscore_normalize_features
)
from schemas.common import (
    NormalizeFeaturesRequest,
    NormalizeFeaturesResponse
)

@handle_operation(exc_type = (ValueError, TypeError))
async def normalize_features(
    request_body: NormalizeFeaturesRequest
) -> NormalizeFeaturesResponse:
    '''
    Normalizes a feature matrix using Z-score normalization.
    '''
    x_matrix = np.array(request_body.x_matrix)
    x_norm, mu, sigma = zscore_normalize_features(x_matrix)

    message = f'Z-score normalization completed for a feature matrix of shape {
        x_matrix.shape}. The calculated mean (mu) is {mu
        } and the standard deviation (sigma) is {sigma}'
    logger.info(message)

    return NormalizeFeaturesResponse(
        x_norm = x_norm.tolist(),
        mu = mu.tolist(),
        sigma = sigma.tolist()
    )
