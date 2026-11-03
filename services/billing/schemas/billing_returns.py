'''
    Returns of an invoiced sale: the Nota de Crédito-Débito.

    When a buyer gives back all or part of what an accepted invoice sold, the
    invoice is not touched: it stays the legal record of the sale. The return
    is a document of its own, the Nota de Crédito-Débito (sector document 24),
    which the SIN receives through its adjustment service and which carries
    the original invoice and what came back (RND 102100000011, art. 36;
    `docs/siat/SIAT.md`, «Nota de Crédito-Débito»).

    Accepted, everything goes back to where it was: the units to the batches
    they left, the money to the buyer by the means they paid with.
'''
from enum import Enum

from pydantic import BaseModel, Field

from schemas.billing import Buyer, InvoiceLine, Payment, SaleAllocation
from schemas.billing_siat import InvoiceState, SaleInvoice

# The SIN's codes for this document: sector document 24 in its catalogue of
# sector documents, invoice type 3 («DOCUMENTO DE AJUSTE») in its catalogue
# of invoice types. Both were read from the catalogues synced for the pilot.
SECTOR_DOCUMENT_CREDIT_DEBIT = 24
INVOICE_TYPE_ADJUSTMENT = 3

# `codigoDetalleTransaccion`: each detail says whether it is the original
# sale or what is being returned.
DETAIL_ORIGINAL = 1
DETAIL_RETURNED = 2


class ReturnError(str, Enum):
    '''
        Why a return was refused.
    '''
    SALE_CANCELLED = 'SALE_CANCELLED'
    INVOICE_NOT_ACCEPTED = 'INVOICE_NOT_ACCEPTED'
    RETURN_DEADLINE_PASSED = 'RETURN_DEADLINE_PASSED'
    RETURN_EXCEEDS_SOLD = 'RETURN_EXCEEDS_SOLD'
    SKU_NOT_IN_SALE = 'SKU_NOT_IN_SALE'
    REFUND_ONLY_BY_RETURN = 'REFUND_ONLY_BY_RETURN'
    REFUND_TILL_CLOSED = 'REFUND_TILL_CLOSED'
    CREDIT_NOTE_NOT_FOUND = 'CREDIT_NOTE_NOT_FOUND'
    CREDIT_NOTE_CANCELLED = 'CREDIT_NOTE_CANCELLED'
    SALE_HAS_RETURNS = 'SALE_HAS_RETURNS'


class ReturnLineIn(BaseModel):
    '''
        One product given back, and how many units.
    '''
    sku: str = Field(..., min_length = 1, max_length = 40)
    quantity: float = Field(..., gt = 0)


class SaleReturnIn(BaseModel):
    '''
        What the buyer gives back.
    '''
    lines: list[ReturnLineIn] = Field(..., min_length = 1)


class SaleReturn(BaseModel):
    '''
        Which sale is being returned and what comes back. The sale and its
        lines address one return; neither means anything without the other.
    '''
    sale_id: str = Field(..., min_length = 1, max_length = 120)
    body: SaleReturnIn


class CreditNoteLineOut(BaseModel):
    '''
        One returned product, with the batches its units go back to.
    '''
    sku: str
    description: str
    quantity: float
    discount: float = Field(..., description = 'The share of the line discount returned.')
    total: float
    allocations: list[SaleAllocation]


class CreditNoteOut(BaseModel):
    '''
        A Nota de Crédito-Débito as it was issued.
    '''
    credit_note_id: str
    sale_id: str
    number: int = Field(..., description = 'numeroNotaCreditoDebito, its own sequence.')
    cuf: str
    cufd: str
    issued_at: str
    state: InvoiceState
    reception_code: str | None = None
    siat_state: str | None = None
    lines: list[CreditNoteLineOut]
    amount_returned: float
    tax_credit: float = Field(..., description = 'montoEfectivoCreditoDebito: 13 % of it.')
    refunds: list[Payment] = Field(
        ..., description = 'What goes back to the buyer by each means they paid with.'
    )
    created_by: str
    created_at: str
    refund_session_id: str | None = Field(
        None, description = 'The till the cash refund left; empty when no cash went back.'
    )
    refund_movement_id: str | None = None
    cancellation_reason: int | None = Field(
        None, description = 'Code of CANCELLATION_REASONS, once cancelled at the SIN.'
    )
    cancelled_at: str | None = None
    cancelled_by: str | None = None
    qr_url: str = Field(..., description = 'Link the printed QR carries, to check it at the SIN.')
    emailed_at: str | None = Field(None, description = 'When SES took the mail to the buyer; '
                                                       'None when it was never sent.')
    reverted_at: str | None = Field(
        None, description = 'When the SIN reverted its cancellation; never cancelled again.'
    )
    reverted_by: str | None = None


class CreditNoteRef(BaseModel):
    '''
        Which note of which sale: the two address one note.
    '''
    sale_id: str = Field(..., min_length = 1, max_length = 120)
    credit_note_id: str = Field(..., min_length = 1, max_length = 60)


class CreditNoteCancelIn(BaseModel):
    '''
        Why a note is cancelled: the SIN cancels one only with a reason from
        its catalogue, as it does an invoice.
    '''
    reason_code: int = Field(..., ge = 1, description = 'Code of CANCELLATION_REASONS.')


class CreditNoteCancellation(CreditNoteRef):
    '''
        Which note of which sale is cancelled, and why: the SIN cancels one
        only with a reason from its catalogue.
    '''
    reason_code: int = Field(..., ge = 1, description = 'Code of CANCELLATION_REASONS.')


class CreditNotesResponse(BaseModel):
    '''
        The returns of one sale, oldest first.
    '''
    items: list[CreditNoteOut]
    total: int


class CreditNoteIssuer(BaseModel):
    '''
        Who issues a note, and with which codes: what the sale does not say.
    '''
    nit: str
    trade_name: str
    municipality: str
    phone: str | None = None
    branch: int
    point_of_sale: int | None = None
    address: str
    cufd: str


class CreditNoteDocument(BaseModel):
    '''
        A note as its XML needs it: its number and CUF, the invoice it adjusts,
        the amounts and both sets of details.
    '''
    number: int
    cuf: str
    issued_at: str
    buyer: Buyer
    invoice: SaleInvoice
    original_total: float
    returned_total: float
    tax_credit: float
    legend: str
    user: str
    original: list[InvoiceLine]
    returned: list[InvoiceLine]
