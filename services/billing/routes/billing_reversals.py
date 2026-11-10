'''
    Reverting a cancellation: HTTP layer.

    Only whoever runs the shop reverts a cancellation, as only they cancel
    (`routes/billing.py`, `routes/billing_returns.py`). The owner is the shop
    the token names, never a parameter.
'''
from boto3.resources.base import ServiceResource
from fastapi import APIRouter, Depends, Path, Request

from core.db_connection_dydb import GET_DB_DEPENDENCY
from core.logger_config import custom_logger as logger
from core.security import get_current_user, require_roles
from controllers.billing_reversals import (
    revert_credit_note_cancellation_controller,
    revert_sale_cancellation_controller
)
from routes.billing_returns import MANAGERS, credit_note_ref
from schemas.billing import SaleNoteOut
from schemas.billing_returns import CreditNoteOut, CreditNoteRef

router = APIRouter(prefix = '/v1/billing/sales', tags = ['Billing — Reversals'])


@router.post('/{sale_id}/revert-cancellation', response_model = SaleNoteOut)
async def revert_sale_cancellation_endpoint(
    request: Request,
    sale_id: str = Path(..., min_length = 1, max_length = 120),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(require_roles(*MANAGERS)),
    current_user: str = Depends(get_current_user)
) -> SaleNoteOut:
    ''' Endpoint to make a cancelled invoice valid again, once. '''
    message = f'Shop {owner}: {current_user} reverts the cancellation of sale {sale_id}.'
    logger.info(message)
    return await revert_sale_cancellation_controller(
        dynamodb_resource = dynamodb_resource, owner = owner, sale_id = sale_id,
        request = request, current_user = current_user
    )


@router.post('/{sale_id}/returns/{credit_note_id}/revert-cancellation',
             response_model = CreditNoteOut)
async def revert_credit_note_cancellation_endpoint(
    request: Request,
    ref: CreditNoteRef = Depends(credit_note_ref),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(require_roles(*MANAGERS)),
    current_user: str = Depends(get_current_user)
) -> CreditNoteOut:
    ''' Endpoint to make a cancelled Nota de Crédito-Débito valid again, once. '''
    message = (f'Shop {owner}: {current_user} reverts the cancellation of credit note '
               f'{ref.credit_note_id} of sale {ref.sale_id}.')
    logger.info(message)
    return await revert_credit_note_cancellation_controller(
        dynamodb_resource = dynamodb_resource, owner = owner, ref = ref,
        request = request, current_user = current_user
    )
