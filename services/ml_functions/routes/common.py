'''
    Common: routes handler
'''
from fastapi import APIRouter, Depends

from controllers.common import (
    normalize_features
)
from schemas.common import (
    NormalizeFeaturesRequest,
    NormalizeFeaturesResponse
)
from services.security import get_current_user
from services.logger_config import custom_logger as logger

router = APIRouter(prefix = '/v1/common', tags = ['ML Common Functions'])

@router.post(
    '/normalize-features',
    response_model = NormalizeFeaturesResponse,
    summary = "Normalize features using Z-score",
    description = '''Normalizes a feature matrix X using Z-score normalization.'''
)
async def normalize_features_algorithm(
    request: NormalizeFeaturesRequest,
    current_user: str = Depends(get_current_user)):
    '''
        Normalizes a feature matrix X using Z-score normalization.

        This endpoint takes a feature matrix X in the request body,
        normalizes it by column (calculating the mean and standard deviation for each column),
        and returns the normalized matrix along with the means and standard deviations used.
        Authentication is required.

        Args:
        request (NormalizeFeaturesRequest): A Pydantic model containing the matrix X to be 
        normalized.
        current_user (str): The authenticated user's identifier (dependency-injected).

        Returns:
        NormalizeFeaturesResponse: An object containing 'x_norm' (normalized matrix),
        'mu' (list of means), and 'sigma' (list of standard deviations).

        Raises:
        UnauthorizedError: If authentication fails.
        ServiceUnavailableError: If an internal server error occurs during the calculation.
    '''
    message = f'User: {current_user} requested Z-score normalization for a feature matrix.'
    logger.info(message)
    return await normalize_features(request)
