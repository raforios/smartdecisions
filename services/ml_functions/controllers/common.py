'''
    Common controller for ML operations
'''
from schemas.common import NormalizeFeaturesRequest, NormalizeFeaturesResponse
from services import training
from services.utils import handle_operation


@handle_operation(exc_type = (ValueError, TypeError))
async def normalize_features(
    request_body: NormalizeFeaturesRequest
) -> NormalizeFeaturesResponse:
    '''
        Normalizes a feature matrix by column (z-score).
    '''
    return training.normalize(request_body)
