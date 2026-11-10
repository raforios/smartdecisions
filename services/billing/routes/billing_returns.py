'''
    Returns of an invoiced sale: HTTP layer.

    Only whoever runs the shop takes a sale back, as only they cancel one
    (`routes/billing.py`): the note goes to the SIN in the shop's name and the
    money leaves their till. The owner is the shop the token names, never a
    parameter.
'''
from boto3.resources.base import ServiceResource
from fastapi import APIRouter, Body, Depends, Path, Request

from core.db_connection import GET_DB_DEPENDENCY
from core.logger_config import custom_logger as logger
from core.security import get_current_user, require_roles
from controllers.billing_returns import (
    cancel_credit_note_controller,
    credit_note_qr_controller,
    list_credit_notes_controller,
    return_sale_controller
)
from schemas.billing_returns import (
    CreditNoteCancelIn,
    CreditNoteCancellation,
    CreditNoteOut,
    CreditNoteRef,
    CreditNotesResponse,
    SaleReturn,
    SaleReturnIn
)
from schemas.billing_siat import InvoiceQrOut

router = APIRouter(prefix = '/v1/billing/sales', tags = ['Billing — Returns'])

# Same pair that runs the shop in `routes/billing.py`.
MANAGERS = ('ADMIN', 'MANAGER')


def sale_return_request(
    body: SaleReturnIn = Body(...),
    sale_id: str = Path(..., min_length = 1, max_length = 120)
) -> SaleReturn:
    '''
        The path and the body of a return, as one DTO.
    '''
    return SaleReturn(sale_id = sale_id, body = body)


def credit_note_ref(
    sale_id: str = Path(..., min_length = 1, max_length = 120),
    credit_note_id: str = Path(..., min_length = 1, max_length = 60)
) -> CreditNoteRef:
    '''
        Which note of which sale, from the path, as one DTO.
    '''
    return CreditNoteRef(sale_id = sale_id, credit_note_id = credit_note_id)


def credit_note_cancellation(
    cancel: CreditNoteCancelIn = Body(...),
    sale_id: str = Path(..., min_length = 1, max_length = 120),
    credit_note_id: str = Path(..., min_length = 1, max_length = 60)
) -> CreditNoteCancellation:
    '''
        Which note of which sale is cancelled, and why, as one DTO.
    '''
    return CreditNoteCancellation(sale_id = sale_id, credit_note_id = credit_note_id,
                                  reason_code = cancel.reason_code)


@router.post('/{sale_id}/returns', response_model = CreditNoteOut, status_code = 201)
async def return_sale_endpoint(
    request: Request,
    sale_return: SaleReturn = Depends(sale_return_request),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(require_roles(*MANAGERS)),
    current_user: str = Depends(get_current_user)
) -> CreditNoteOut:
    ''' Endpoint to take back all or part of an invoiced sale. '''
    message = (f'Shop {owner}: {current_user} returns {len(sale_return.body.lines)} '
               f'line(s) of sale {sale_return.sale_id}.')
    logger.info(message)
    return await return_sale_controller(
        dynamodb_resource = dynamodb_resource, owner = owner, sale_return = sale_return,
        request = request, current_user = current_user
    )


@router.get('/{sale_id}/returns', response_model = CreditNotesResponse)
async def list_credit_notes_endpoint(
    request: Request,
    sale_id: str = Path(..., min_length = 1, max_length = 120),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(require_roles(*MANAGERS)),
    current_user: str = Depends(get_current_user)
) -> CreditNotesResponse:
    ''' Endpoint for the returns of one sale. '''
    return await list_credit_notes_controller(
        dynamodb_resource = dynamodb_resource, owner = owner, sale_id = sale_id,
        request = request, current_user = current_user
    )


@router.post('/{sale_id}/returns/{credit_note_id}/cancel', response_model = CreditNoteOut)
async def cancel_credit_note_endpoint(
    request: Request,
    cancellation: CreditNoteCancellation = Depends(credit_note_cancellation),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(require_roles(*MANAGERS)),
    current_user: str = Depends(get_current_user)
) -> CreditNoteOut:
    ''' Endpoint to cancel a Nota de Crédito-Débito and undo its return. '''
    message = (f'Shop {owner}: {current_user} cancels credit note '
               f'{cancellation.credit_note_id} of sale {cancellation.sale_id}.')
    logger.info(message)
    return await cancel_credit_note_controller(
        dynamodb_resource = dynamodb_resource, owner = owner, cancellation = cancellation,
        request = request, current_user = current_user
    )


@router.get('/{sale_id}/returns/{credit_note_id}/qr', response_model = InvoiceQrOut)
async def credit_note_qr_endpoint(
    request: Request,
    ref: CreditNoteRef = Depends(credit_note_ref),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(require_roles(*MANAGERS)),
    current_user: str = Depends(get_current_user)
) -> InvoiceQrOut:
    ''' Endpoint for the QR a note prints. '''
    return await credit_note_qr_controller(
        dynamodb_resource = dynamodb_resource, owner = owner, ref = ref,
        request = request, current_user = current_user
    )
