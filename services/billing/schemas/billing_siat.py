'''
    Electronic invoicing with the SIN: the contract of the codes and catalogues
    a shop needs before it can issue a single invoice.

    The CUIS identifies the system at one branch and point of sale for a year;
    the CUFD, valid one day, closes the CUF of every invoice of that day. Both
    are issued by the tax office and stored per shop, branch and point of sale.

    The catalogues are the SIN's own lists —legends, payment methods, units,
    reasons to cancel— and every invoice must use their codes. They are
    synchronised from the tax office and stored per shop, because the
    activities and products depend on the shop's NIT.
'''
from enum import Enum

from pydantic import BaseModel, Field


class SiatCatalog(str, Enum):
    '''
        The catalogues of the synchronisation service, named after what they
        hold. The SIN operation that brings each one lives in the client.
    '''
    ACTIVITIES = 'ACTIVITIES'
    SECTOR_DOCUMENT_ACTIVITIES = 'SECTOR_DOCUMENT_ACTIVITIES'
    LEGENDS = 'LEGENDS'
    SERVICE_MESSAGES = 'SERVICE_MESSAGES'
    PRODUCTS_AND_SERVICES = 'PRODUCTS_AND_SERVICES'
    SIGNIFICANT_EVENTS = 'SIGNIFICANT_EVENTS'
    CANCELLATION_REASONS = 'CANCELLATION_REASONS'
    COUNTRIES = 'COUNTRIES'
    IDENTITY_DOCUMENT_TYPES = 'IDENTITY_DOCUMENT_TYPES'
    SECTOR_DOCUMENT_TYPES = 'SECTOR_DOCUMENT_TYPES'
    EMISSION_TYPES = 'EMISSION_TYPES'
    ROOM_TYPES = 'ROOM_TYPES'
    PAYMENT_METHODS = 'PAYMENT_METHODS'
    CURRENCIES = 'CURRENCIES'
    POINT_OF_SALE_TYPES = 'POINT_OF_SALE_TYPES'
    INVOICE_TYPES = 'INVOICE_TYPES'
    UNITS_OF_MEASURE = 'UNITS_OF_MEASURE'


class CatalogEntry(BaseModel):
    '''
        One row of a SIN catalogue, whatever its shape.

        The SIN returns five shapes —parametrics, activities, products, legends
        and the activity of each sector document—. All of them are a code and
        its description, and three of them hang from an economic activity; so
        one row keeps the three, and the catalogue it came from says how to
        read them.
    '''
    code: str = Field(..., description = 'Code the invoice carries. Empty for a legend.')
    description: str = Field(..., description = 'As the SIN writes it.')
    activity_code: str | None = Field(
        None, description = 'Economic activity it belongs to, when it belongs to one.'
    )


class CatalogOut(BaseModel):
    '''
        One stored catalogue and when it was brought from the tax office.
    '''
    catalog: SiatCatalog
    synced_at: str
    entries: list[CatalogEntry]


class CatalogSummary(BaseModel):
    '''
        How many rows one catalogue brought in a synchronisation.
    '''
    catalog: SiatCatalog
    entries: int


class CatalogsSyncResponse(BaseModel):
    '''
        The result of synchronising every catalogue.
    '''
    synced_at: str
    catalogs: list[CatalogSummary]


class SiatCodesOut(BaseModel):
    '''
        The codes in force for the shop's branch and point of sale.
    '''
    branch: int
    point_of_sale: int
    cuis: str
    cuis_valid_until: str
    cufd: str
    control_code: str
    cufd_valid_until: str
    address: str = Field(..., description = 'Address the SIN has registered for the CUFD.')


class InvoiceState(str, Enum):
    '''
        Where an invoice stands with the tax office.

        Only the accepted state exists today: a sale whose invoice the SIN
        refuses or cannot receive is not issued at all. The offline states
        arrive with contingency.
    '''
    ACCEPTED = 'ACCEPTED'
    CANCELLED = 'CANCELLED'


class SaleInvoice(BaseModel):
    '''
        The invoice a sale became, as it prints and as the SIN knows it.
    '''
    number: int = Field(..., ge = 1, description = 'Invoice number, per branch and point of sale.')
    cuf: str
    cufd: str
    issued_at: str = Field(..., description = 'fechaEmision, exactly as it went in the XML.')
    legend: str
    address: str = Field(..., description = 'Address the SIN registered for the CUFD.')
    branch: int = Field(..., description = 'As it went into the CUF; 0 is the head office.')
    point_of_sale: int = Field(..., description = 'As it went into the CUF; 0 when none.')
    state: InvoiceState
    reception_code: str | None = None
    siat_state: str | None = Field(None, description = 'codigoEstado the SIN answered.')
    qr_url: str = Field(..., description = 'Link the printed QR carries, to check it at the SIN.')
    cancellation_reason: int | None = Field(
        None, description = 'Code of CANCELLATION_REASONS, once cancelled at the SIN.'
    )


class InvoiceQrOut(BaseModel):
    '''
        The QR the invoice prints, drawn from the link it stored.
    '''
    sale_id: str
    # Inline SVG with no fixed size: the ticket's box sizes it.
    svg: str


class SaleCancelIn(BaseModel):
    '''
        Why a note is cancelled. Only an invoiced note needs it: the SIN
        cancels an invoice only with a reason from its catalogue.
    '''
    reason_code: int | None = Field(None, ge = 1,
                                    description = 'Code of CANCELLATION_REASONS.')


class SaleCancellation(SaleCancelIn):
    '''
        Which note is cancelled, and why.
    '''
    sale_id: str = Field(..., min_length = 1, max_length = 120)
