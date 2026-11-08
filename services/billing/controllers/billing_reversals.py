'''
    Reverting a cancellation: orchestration between the HTTP layer and the
    services.

    Same contract as `controllers/billing.py`: every controller carries
    `@handle_service_errors`, and every one that changes something carries
    `@audit_event`.
'''
from boto3.resources.base import ServiceResource
from fastapi import Request

from schemas.billing import SaleNoteOut
from schemas.billing_returns import CreditNoteOut, CreditNoteRef
from services import billing_reversals
from services.billing_bridge import share_cancellation, share_return
from services.billing_movements import share_movement
from services.utils import audit_event, handle_service_errors

SERVICE = 'BILLING'


@handle_service_errors(SERVICE)
@audit_event(SERVICE, 'Sale', 'REVERT_CANCELLATION', id_field = 'sale_id')
async def revert_sale_cancellation_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    sale_id: str,
    request: Request,
    current_user: str
) -> SaleNoteOut:
    '''
        Makes a cancelled invoice valid again, and tells SmartDecisions when
        the shop wants it.
    '''
    sale = billing_reversals.revert_sale_cancellation(dynamodb_resource, owner, sale_id,
                                                      current_user)
    share_cancellation(dynamodb_resource, owner, sale.sale_id, request)
    share_movement(dynamodb_resource, owner, sale.created_at, request)
    return sale


@handle_service_errors(SERVICE)
@audit_event(SERVICE, 'CreditNote', 'REVERT_CANCELLATION', id_field = 'credit_note_id')
async def revert_credit_note_cancellation_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    ref: CreditNoteRef,
    request: Request,
    current_user: str
) -> CreditNoteOut:
    '''
        Makes a cancelled Nota de Crédito-Débito valid again, and tells
        SmartDecisions when the shop wants it.
    '''
    note = billing_reversals.revert_credit_note_cancellation(dynamodb_resource, owner, ref,
                                                             current_user)
    share_return(dynamodb_resource, owner, note, request)
    share_movement(dynamodb_resource, owner, note.issued_at, request)
    return note
