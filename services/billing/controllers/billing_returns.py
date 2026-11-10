'''
    Returns of an invoiced sale: orchestration between the HTTP layer and the
    services.

    Same contract as `controllers/billing.py`: every controller carries
    `@handle_service_errors`, and every one that changes something carries
    `@audit_event`.
'''
from boto3.resources.base import ServiceResource
from fastapi import Request

from core.utils import audit_event, handle_service_errors
from schemas.billing_returns import (
    CreditNoteCancellation,
    CreditNoteOut,
    CreditNoteRef,
    CreditNotesResponse,
    SaleReturn
)
from schemas.billing_siat import InvoiceQrOut
from services import billing_returns
from services.billing_bridge import share_return
from services.billing_movements import share_movement

SERVICE = 'BILLING'


@handle_service_errors(SERVICE)
@audit_event(SERVICE, 'CreditNote', 'ISSUE', id_field = 'credit_note_id')
async def return_sale_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    sale_return: SaleReturn,
    request: Request,
    current_user: str
) -> CreditNoteOut:
    '''
        Takes back all or part of an invoiced sale with a Nota de Crédito-Débito,
        and tells SmartDecisions when the shop wants it.
    '''
    note = billing_returns.return_sale(dynamodb_resource, owner, sale_return, current_user)
    share_return(dynamodb_resource, owner, note, request)
    share_movement(dynamodb_resource, owner, note.issued_at, request)
    return note


@handle_service_errors(SERVICE)
async def list_credit_notes_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    sale_id: str,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> CreditNotesResponse:
    '''
        The returns of one sale.
    '''
    return billing_returns.list_credit_notes(dynamodb_resource, owner, sale_id)


@handle_service_errors(SERVICE)
@audit_event(SERVICE, 'CreditNote', 'CANCEL', id_field = 'credit_note_id')
async def cancel_credit_note_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    cancellation: CreditNoteCancellation,
    request: Request,
    current_user: str
) -> CreditNoteOut:
    '''
        Cancels a Nota de Crédito-Débito, undoes its return, and tells
        SmartDecisions when the shop wants it.
    '''
    note = billing_returns.cancel_credit_note(dynamodb_resource, owner, cancellation,
                                              current_user)
    share_return(dynamodb_resource, owner, note, request)
    share_movement(dynamodb_resource, owner, note.issued_at, request)
    return note


@handle_service_errors(SERVICE)
async def credit_note_qr_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    ref: CreditNoteRef,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> InvoiceQrOut:
    '''
        The QR a note prints.
    '''
    return billing_returns.credit_note_qr(dynamodb_resource, owner, ref)
