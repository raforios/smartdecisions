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

        OFFLINE is an invoice issued while the SIN could not be reached: it is
        valid on paper and waits for its package. OBSERVED is one the SIN
        returned with errors in that package.
    '''
    ACCEPTED = 'ACCEPTED'
    CANCELLED = 'CANCELLED'
    OFFLINE = 'OFFLINE'
    OBSERVED = 'OBSERVED'


class SignificantEvent(int, Enum):
    '''
        The SIN's significant events, by the code of its catalogue. The first
        four are issued offline by this system; the last three need the
        manual contingency invoices (CAFC).
    '''
    INTERNET_CUT = 1
    SIN_UNREACHABLE = 2
    ZONE_WITHOUT_INTERNET = 3
    SALE_WITHOUT_INTERNET = 4
    VIRUS_OR_SOFTWARE_FAILURE = 5
    INFRASTRUCTURE_OR_HARDWARE_FAILURE = 6
    POWER_CUT = 7


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
    emission_type: int = Field(1, description = '1 online, 2 offline: it changes the legend.')
    package_reception_code: str | None = None
    observations: list[str] = Field(default_factory = list,
                                    description = 'What the SIN observed, verbatim.')
    emailed_at: str | None = Field(None, description = 'When SES took the mail to the buyer; '
                                                       'None when it was never sent.')
    cafc: str | None = Field(None, description = 'Only on a transcribed paper contingency invoice.')


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


class PackageReceipt(BaseModel):
    '''
        What the SIN answered about a package of offline invoices.

        `observed` maps the position of a file in the package, from zero, to
        the SIN's messages about it, verbatim.
    '''
    accepted: bool
    reception_code: str | None = None
    state: str | None = None
    messages: list[str] = Field(default_factory = list)
    observed: dict[int, list[str]] = Field(default_factory = dict)


class ContingencyIn(BaseModel):
    '''
        A contingency entered by hand: the SIN cannot be reached and the shop
        knows it before the system does — a point of sale with no internet.
    '''
    event: SignificantEvent = Field(..., le = SignificantEvent.SALE_WITHOUT_INTERNET,
                                    description = 'Only the events issued offline (1 to 4).')


class ContingencyOut(BaseModel):
    '''
        A point of sale issuing offline.
    '''
    branch: int
    point_of_sale: int
    event: SignificantEvent
    started_at: str
    cufd: str = Field(..., description = 'The CUFD the offline invoices carry.')
    last_check_at: str | None = None
    pending_invoices: int = 0


class ContingencyStatus(BaseModel):
    '''
        Whether the shop's point of sale is offline, and since when.
    '''
    offline: bool
    contingency: ContingencyOut | None = None


class RecoveryOut(BaseModel):
    '''
        What one attempt to leave contingency did.
    '''
    recovered: bool = Field(..., description = 'False while the SIN still does not answer.')
    event_reception_code: int | None = None
    packages: list[PackageReceipt] = Field(default_factory = list)
    invoices_sent: int = 0
    invoices_observed: int = 0
    uncertain_cancelled: int = Field(
        0, description = 'Online sendings cut without answer that the SIN had '
                         'registered, cancelled so the offline twin is the only one.'
    )
