'''
    Manual contingency invoices: HTTP layer.

    Only whoever runs the shop registers a CAFC, opens a manual contingency,
    transcribes its paper invoices and sends them: each step talks to the SIN
    in the shop's name. The owner is the shop the token names, never a
    parameter.
'''
from boto3.resources.base import ServiceResource
from fastapi import APIRouter, Body, Depends, Path, Request

from controllers.billing_manual import (
    list_cafcs_controller,
    list_manual_contingencies_controller,
    open_manual_contingency_controller,
    register_cafc_controller,
    send_manual_contingency_controller,
    transcribe_invoice_controller
)
from schemas.billing import SaleNoteOut
from schemas.billing_manual import (
    CafcIn,
    CafcOut,
    CafcsResponse,
    ManualContingenciesResponse,
    ManualContingencyIn,
    ManualContingencyOut,
    ManualInvoiceIn,
    ManualTranscription
)
from schemas.billing_siat import RecoveryOut
from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger
from services.security import get_current_user, require_roles

router = APIRouter(prefix = '/v1/billing/siat', tags = ['Billing — Manual contingency'])

# Same pair that runs the shop in `routes/billing.py`.
MANAGERS = ('ADMIN', 'MANAGER')


def manual_transcription(
    invoice: ManualInvoiceIn = Body(...),
    contingency_id: str = Path(..., min_length = 1, max_length = 120)
) -> ManualTranscription:
    '''
        The path and the body of a transcription, as one DTO.
    '''
    return ManualTranscription(contingency_id = contingency_id, invoice = invoice)


@router.get('/cafc', response_model = CafcsResponse)
async def list_cafcs_endpoint(
    request: Request,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(require_roles(*MANAGERS)),
    current_user: str = Depends(get_current_user)
) -> CafcsResponse:
    ''' Endpoint for the shop's CAFCs. '''
    return await list_cafcs_controller(
        dynamodb_resource = dynamodb_resource, owner = owner,
        request = request, current_user = current_user
    )


@router.post('/cafc', response_model = CafcOut, status_code = 201)
async def register_cafc_endpoint(
    cafc: CafcIn,
    request: Request,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(require_roles(*MANAGERS)),
    current_user: str = Depends(get_current_user)
) -> CafcOut:
    ''' Endpoint to register a CAFC and its range. '''
    message = f'Shop {owner}: {current_user} registers CAFC {cafc.cafc}.'
    logger.info(message)
    return await register_cafc_controller(
        dynamodb_resource = dynamodb_resource, owner = owner, cafc = cafc,
        request = request, current_user = current_user
    )


@router.get('/manual-contingencies', response_model = ManualContingenciesResponse)
async def list_manual_contingencies_endpoint(
    request: Request,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(require_roles(*MANAGERS)),
    current_user: str = Depends(get_current_user)
) -> ManualContingenciesResponse:
    ''' Endpoint for the shop's manual contingencies. '''
    return await list_manual_contingencies_controller(
        dynamodb_resource = dynamodb_resource, owner = owner,
        request = request, current_user = current_user
    )


@router.post('/manual-contingencies', response_model = ManualContingencyOut,
             status_code = 201)
async def open_manual_contingency_endpoint(
    contingency: ManualContingencyIn,
    request: Request,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(require_roles(*MANAGERS)),
    current_user: str = Depends(get_current_user)
) -> ManualContingencyOut:
    ''' Endpoint to open a contingency of paper invoices. '''
    message = f'Shop {owner}: {current_user} opens a manual contingency ({contingency.cafc}).'
    logger.info(message)
    return await open_manual_contingency_controller(
        dynamodb_resource = dynamodb_resource, owner = owner, contingency = contingency,
        request = request, current_user = current_user
    )


@router.post('/manual-contingencies/{contingency_id}/invoices', response_model = SaleNoteOut,
             status_code = 201)
async def transcribe_invoice_endpoint(
    request: Request,
    transcription: ManualTranscription = Depends(manual_transcription),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(require_roles(*MANAGERS)),
    current_user: str = Depends(get_current_user)
) -> SaleNoteOut:
    ''' Endpoint to transcribe one paper invoice. '''
    message = (f'Shop {owner}: {current_user} transcribes paper invoice '
               f'{transcription.invoice.number}.')
    logger.info(message)
    return await transcribe_invoice_controller(
        dynamodb_resource = dynamodb_resource, owner = owner, transcription = transcription,
        request = request, current_user = current_user
    )


@router.post('/manual-contingencies/{contingency_id}/send', response_model = RecoveryOut)
async def send_manual_contingency_endpoint(
    request: Request,
    contingency_id: str = Path(..., min_length = 1, max_length = 120),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(require_roles(*MANAGERS)),
    current_user: str = Depends(get_current_user)
) -> RecoveryOut:
    ''' Endpoint to send the transcribed invoices to the SIN. '''
    message = f'Shop {owner}: {current_user} sends manual contingency {contingency_id}.'
    logger.info(message)
    return await send_manual_contingency_controller(
        dynamodb_resource = dynamodb_resource, owner = owner, contingency_id = contingency_id,
        request = request, current_user = current_user
    )
