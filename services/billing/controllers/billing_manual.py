'''
    Manual contingency invoices: orchestration between the HTTP layer and the
    services.

    Same contract as `controllers/billing.py`: every controller carries
    `@handle_service_errors`, and every one that changes something carries
    `@audit_event`.
'''
from boto3.resources.base import ServiceResource
from fastapi import Request

from schemas.billing import SaleNoteOut
from schemas.billing_manual import (
    CafcIn,
    CafcOut,
    CafcsResponse,
    ManualContingenciesResponse,
    ManualContingencyIn,
    ManualContingencyOut,
    ManualTranscription
)
from schemas.billing_siat import RecoveryOut
from services import billing_manual
from services.utils import audit_event, handle_service_errors

SERVICE = 'BILLING'


@handle_service_errors(SERVICE)
async def list_cafcs_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> CafcsResponse:
    '''
        The shop's CAFCs.
    '''
    return billing_manual.list_cafcs(dynamodb_resource, owner)


@handle_service_errors(SERVICE)
@audit_event(SERVICE, 'SiatCafc', 'CREATE', id_field = 'cafc')
async def register_cafc_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    cafc: CafcIn,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> CafcOut:
    '''
        Keeps a CAFC and its range.
    '''
    return billing_manual.register_cafc(dynamodb_resource, owner, cafc)


@handle_service_errors(SERVICE)
async def list_manual_contingencies_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> ManualContingenciesResponse:
    '''
        The shop's manual contingencies.
    '''
    return billing_manual.list_manual_contingencies(dynamodb_resource, owner)


@handle_service_errors(SERVICE)
@audit_event(SERVICE, 'ManualContingency', 'OPEN', id_field = 'contingency_id')
async def open_manual_contingency_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    contingency: ManualContingencyIn,
    request: Request, # pylint: disable=unused-argument
    current_user: str
) -> ManualContingencyOut:
    '''
        Opens a contingency of paper invoices.
    '''
    return billing_manual.open_manual_contingency(dynamodb_resource, owner, contingency,
                                                  current_user)


@handle_service_errors(SERVICE)
@audit_event(SERVICE, 'SaleNote', 'TRANSCRIBE')
async def transcribe_invoice_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    transcription: ManualTranscription,
    request: Request, # pylint: disable=unused-argument
    current_user: str
) -> SaleNoteOut:
    '''
        Transcribes one paper invoice.
    '''
    return billing_manual.transcribe_invoice(dynamodb_resource, owner,
                                             transcription.contingency_id,
                                             transcription.invoice, current_user)


@handle_service_errors(SERVICE)
@audit_event(SERVICE, 'ManualContingency', 'SEND')
async def send_manual_contingency_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    contingency_id: str,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> RecoveryOut:
    '''
        Sends the transcribed invoices to the SIN.
    '''
    return billing_manual.send_manual_contingency(dynamodb_resource, owner, contingency_id)
