'''
    Manual contingency invoices: the paper invoices a shop issues while its
    system cannot work at all, and their transcription afterwards.

    When the system itself is down (a software failure, a hardware failure or
    a power cut: events 5, 6 and 7), the shop issues the paper invoices it had
    printed under a CAFC, a code the SIN authorizes beforehand with its range
    of numbers. Once the system is back, each paper invoice is transcribed
    with its own number, moment and CAFC, and with the CUFD in force when the
    contingency began; then the event is registered and the invoices go to
    the SIN in packages, within 72 hours (`docs/siat/SIAT.md`).
'''
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator

from schemas.billing import Buyer, Payment, PaymentMethod
from schemas.billing_siat import SignificantEvent


class ManualError(str, Enum):
    '''
        Why a CAFC, a manual contingency or a transcription was refused.
    '''
    CAFC_ALREADY_REGISTERED = 'CAFC_ALREADY_REGISTERED'
    CAFC_NOT_FOUND = 'CAFC_NOT_FOUND'
    NUMBER_OUTSIDE_CAFC = 'NUMBER_OUTSIDE_CAFC'
    NUMBER_ALREADY_TRANSCRIBED = 'NUMBER_ALREADY_TRANSCRIBED'
    MANUAL_CONTINGENCY_NOT_FOUND = 'MANUAL_CONTINGENCY_NOT_FOUND'
    MANUAL_CONTINGENCY_SENT = 'MANUAL_CONTINGENCY_SENT'
    ISSUED_OUTSIDE_EVENT = 'ISSUED_OUTSIDE_EVENT'
    CUFD_NOT_KEPT = 'CUFD_NOT_KEPT'
    INVOICING_DISABLED = 'INVOICING_DISABLED'
    NOTHING_TO_SEND = 'NOTHING_TO_SEND'


class ManualContingencyStatus(str, Enum):
    '''
        Where a manual contingency stands.
    '''
    OPEN = 'OPEN'
    SENT = 'SENT'


class CafcIn(BaseModel):
    '''
        A CAFC the SIN authorized, with the numbers printed under it.
    '''
    cafc: str = Field(..., min_length = 1, max_length = 50)
    first_number: int = Field(..., ge = 1)
    last_number: int = Field(..., ge = 1)

    @model_validator(mode = 'after')
    def _range_goes_up(self) -> 'CafcIn':
        '''
            The range is read from the first number to the last.
        '''
        if self.last_number < self.first_number:
            raise ValueError('last_number must not be below first_number')
        return self


class CafcOut(CafcIn):
    '''
        A registered CAFC and the numbers already transcribed under it.
    '''
    used_numbers: list[int] = Field(default_factory = list)
    registered_at: str


class CafcsResponse(BaseModel):
    '''
        The shop's CAFCs.
    '''
    items: list[CafcOut]


class ManualContingencyIn(BaseModel):
    '''
        A contingency during which paper invoices were issued.
    '''
    cafc: str = Field(..., min_length = 1, max_length = 50)
    event: SignificantEvent = Field(..., ge = SignificantEvent.VIRUS_OR_SOFTWARE_FAILURE,
                                    description = 'Only the events of paper invoices (5 to 7).')
    started_at: datetime = Field(..., description = 'With its offset; when the system went down.')
    ended_at: datetime = Field(..., description = 'With its offset; when it came back.')

    @model_validator(mode = 'after')
    def _ends_after_it_starts(self) -> 'ManualContingencyIn':
        '''
            A contingency ends after it begins.
        '''
        if self.ended_at <= self.started_at:
            raise ValueError('ended_at must be after started_at')
        return self


class ManualContingencyOut(BaseModel):
    '''
        A manual contingency and its transcriptions.
    '''
    contingency_id: str
    cafc: str
    event: SignificantEvent
    started_at: str
    ended_at: str
    cufd: str = Field(..., description = 'The CUFD in force when it began.')
    status: ManualContingencyStatus
    sale_ids: list[str] = Field(default_factory = list)
    event_reception_code: int | None = None
    created_by: str
    created_at: str


class ManualContingenciesResponse(BaseModel):
    '''
        The shop's manual contingencies, newest first.
    '''
    items: list[ManualContingencyOut]


class ManualLineIn(BaseModel):
    '''
        One line as the paper invoice wrote it, price included: what was
        charged then is what the invoice says, whatever the shelf says now.
    '''
    sku: str = Field(..., min_length = 1, max_length = 40)
    quantity: float = Field(..., gt = 0)
    unit_price: float = Field(..., gt = 0)


class ManualInvoiceIn(BaseModel):
    '''
        One paper invoice, transcribed.
    '''
    number: int = Field(..., ge = 1, description = 'As printed on the paper invoice.')
    issued_at: datetime = Field(..., description = 'With its offset; as written on paper.')
    buyer: Buyer
    lines: list[ManualLineIn] = Field(..., min_length = 1)
    payment_method: PaymentMethod = PaymentMethod.EFECTIVO
    payments: list[Payment] | None = Field(None, min_length = 1, max_length = 3)
    card_number: str | None = Field(None, max_length = 30)


class ManualTranscription(BaseModel):
    '''
        A paper invoice and the manual contingency it is transcribed into:
        the path and the body of the endpoint, as one DTO.
    '''
    contingency_id: str = Field(..., min_length = 1, max_length = 120)
    invoice: ManualInvoiceIn
