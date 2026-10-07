'''
    Pharmacy billing: DTOs and error codes.

    The product a pharmacy buys: a catalogue of SKUs, lots received from a
    laboratory or importer, and the two documents that move stock — the nota de
    compra that brings units in and the nota de venta that takes them out.

    Everything here is multi-tenant: the owner is the pharmacy, taken from the
    token, and it is part of every key rather than a filter applied afterwards.

    The backend answers with data and codes; the wording belongs to the
    frontend and to the interpretation layer.
'''
from datetime import date, datetime, time as time_type
from enum import Enum
from typing import Final

from pydantic import BaseModel, Field


# The SIAT numbers its catalogues; only the codes BILLING issues today are
# here, and the rest are added when a trade that needs them is sold to. They
# live with the DTOs because they are contract, not behaviour: the algorithms
# in services/billing_siat.py read them, never the other way round.
MODALITY_ELECTRONIC_ONLINE = 1
MODALITY_COMPUTERIZED_ONLINE = 2

EMISSION_ONLINE = 1
EMISSION_OFFLINE = 2

INVOICE_WITH_TAX_CREDIT = 1
INVOICE_WITHOUT_TAX_CREDIT = 2

SECTOR_DOCUMENT_PURCHASE_SALE = 1


class CufInput(BaseModel):
    '''
        What identifies one invoice uniquely before the SIN.

        The nine fields are the CUF itself: the norm names them and fixes the
        order in which they concatenate, so they are stated here exactly as the
        norm states them. The last four default to what this product issues
        today; the first five belong to the individual document.
    '''
    nit: str = Field(..., max_length = 13, description = 'Issuer\'s NIT.')
    issued_at: datetime = Field(
        ..., description = 'Exact moment of issue, with milliseconds.'
    )
    invoice_number: int = Field(..., ge = 0, description = 'Invoice sequence number.')
    branch: int = Field(0, ge = 0, description = 'Branch; 0 is the head office.')
    point_of_sale: int = Field(
        0, ge = 0, description = 'Point of sale; 0 when it does not apply.'
    )
    modality: int = Field(
        MODALITY_COMPUTERIZED_ONLINE,
        description = '1 electronic online, 2 computerized online.'
    )
    emission_type: int = Field(EMISSION_ONLINE, description = '1 online, 2 offline.')
    invoice_type: int = Field(
        INVOICE_WITH_TAX_CREDIT, description = '1 with tax credit, 2 without.'
    )
    sector_document: int = Field(
        SECTOR_DOCUMENT_PURCHASE_SALE,
        description = 'Sector document type; 1 is purchase-sale.'
    )


class BillingError(str, Enum):
    '''
        Why a pharmacy request could not be served.
    '''
    SKU_ALREADY_EXISTS = 'SKU_ALREADY_EXISTS'
    PRODUCT_NOT_FOUND = 'PRODUCT_NOT_FOUND'
    PRODUCT_INACTIVE = 'PRODUCT_INACTIVE'
    LOT_NOT_FOUND = 'LOT_NOT_FOUND'
    DUPLICATE_LINE = 'DUPLICATE_LINE'
    INSUFFICIENT_STOCK = 'INSUFFICIENT_STOCK'
    DISCOUNTS_DISABLED = 'DISCOUNTS_DISABLED'
    DISCOUNT_ABOVE_LINE = 'DISCOUNT_ABOVE_LINE'
    SALE_NOT_FOUND = 'SALE_NOT_FOUND'
    SALE_ALREADY_CANCELLED = 'SALE_ALREADY_CANCELLED'
    PURCHASE_NOT_FOUND = 'PURCHASE_NOT_FOUND'
    SETTINGS_NOT_FOUND = 'SETTINGS_NOT_FOUND'
    BUYER_REQUIRED = 'BUYER_REQUIRED'
    CARD_WITHOUT_CARD_PAYMENT = 'CARD_WITHOUT_CARD_PAYMENT'
    INVALID_CARD_NUMBER = 'INVALID_CARD_NUMBER'
    PRODUCT_NOT_HOMOLOGATED = 'PRODUCT_NOT_HOMOLOGATED'
    TOO_MANY_LINES = 'TOO_MANY_LINES'
    SIAT_UNREACHABLE = 'SIAT_UNREACHABLE'
    SIAT_WSDL_MISSING = 'SIAT_WSDL_MISSING'
    CASH_SESSION_ALREADY_OPEN = 'CASH_SESSION_ALREADY_OPEN'
    CASH_SESSION_REQUIRED = 'CASH_SESSION_REQUIRED'
    CASH_SESSION_CLOSED = 'CASH_SESSION_CLOSED'
    CASH_SESSION_EXPIRED = 'CASH_SESSION_EXPIRED'
    CASH_SESSION_NOT_FOUND = 'CASH_SESSION_NOT_FOUND'
    CLOSING_NOTE_REQUIRED = 'CLOSING_NOTE_REQUIRED'
    EXPENSE_EXCEEDS_CASH = 'EXPENSE_EXCEEDS_CASH'
    EXPENSE_NOT_FOUND = 'EXPENSE_NOT_FOUND'


class PaymentMethod(str, Enum):
    '''
        How the buyer paid.

        Debit and credit are told apart for the shop's own reports; for the
        SIN both are a card. `TARJETA` stays for the notes issued before the
        distinction existed, which the reports show as a card with no detail.
    '''
    EFECTIVO = 'EFECTIVO'
    QR = 'QR'
    TARJETA = 'TARJETA'
    TARJETA_DEBITO = 'TARJETA_DEBITO'
    TARJETA_CREDITO = 'TARJETA_CREDITO'


CARD_METHODS: Final[frozenset] = frozenset({
    PaymentMethod.TARJETA, PaymentMethod.TARJETA_DEBITO, PaymentMethod.TARJETA_CREDITO
})


# What each of them is called in the SIN's `codigoMetodoPago` parameter. Only
# cash and card have a code of their own; QR travels as OTROS, which is what
# the norm says to use when the method is not in the list
# (`docs/siat/SIAT.md`). The full catalogue is synchronised from the SIN once
# the authorization exists, and may add a code for QR — that is why the map
# lives here and not inlined at the point of use.
SIN_PAYMENT_CASH: int = 1
SIN_PAYMENT_CARD: int = 2
SIN_PAYMENT_OTHER: int = 5

SIN_PAYMENT_CODES: dict = {
    PaymentMethod.EFECTIVO: SIN_PAYMENT_CASH,
    PaymentMethod.TARJETA: SIN_PAYMENT_CARD,
    PaymentMethod.TARJETA_DEBITO: SIN_PAYMENT_CARD,
    PaymentMethod.TARJETA_CREDITO: SIN_PAYMENT_CARD,
    PaymentMethod.QR: SIN_PAYMENT_OTHER
}


class SaleStatus(str, Enum):
    '''
        A sale note is issued once and may later be cancelled, which returns
        the units to the lots they came from. It is never edited: the printed
        paper is already in the buyer's hands.
    '''
    ISSUED = 'ISSUED'
    CANCELLED = 'CANCELLED'


class TicketWidth(str, Enum):
    '''
        Thermal paper the pharmacy prints on. Both are common at a counter.
    '''
    MM_58 = 'MM_58'
    MM_80 = 'MM_80'


# --- catalogue ---------------------------------------------------------------

class ProductIn(BaseModel):
    '''
        A SKU as the pharmacy registers it.
    '''
    sku: str = Field(..., min_length = 1, max_length = 40)
    description: str = Field(..., min_length = 1, max_length = 300)
    laboratory: str = Field(..., min_length = 1, max_length = 150,
                            description = 'Laboratory or importer that supplies it.')
    unit: str = Field('UND', min_length = 1, max_length = 20)
    barcode: str | None = Field(None, max_length = 60)
    min_stock: float = Field(0, ge = 0)
    requires_prescription: bool = False
    is_active: bool = True
    # Homologation before the SIN. Without these three codes the electronic
    # invoice is rejected, so they are asked for from the start even though
    # nothing is sent yet: asking later would mean walking a whole catalogue
    # product by product.
    sin_activity_code: str | None = Field(
        None, max_length = 20, description = 'Actividad económica del emisor (ej. 451010).'
    )
    sin_product_code: str | None = Field(
        None, max_length = 20, description = 'Código de producto/servicio del SIN.'
    )
    sin_unit_code: int | None = Field(
        None, ge = 1, le = 200, description = 'Unidad de medida del catálogo del SIN.'
    )


class ProductPatch(BaseModel):
    '''
        What may change about a SKU after it was registered. The SKU itself
        never does: it is the key the lots and the sold lines point at.
    '''
    description: str | None = Field(None, min_length = 1, max_length = 300)
    laboratory: str | None = Field(None, min_length = 1, max_length = 150)
    unit: str | None = Field(None, min_length = 1, max_length = 20)
    barcode: str | None = Field(None, max_length = 60)
    min_stock: float | None = Field(None, ge = 0)
    requires_prescription: bool | None = None
    is_active: bool | None = None
    sin_activity_code: str | None = Field(None, max_length = 20)
    sin_product_code: str | None = Field(None, max_length = 20)
    sin_unit_code: int | None = Field(None, ge = 1, le = 200)


class ProductOut(BaseModel):
    '''
        A SKU with the stock its lots add up to.

        `sale_price` is the price of the lot that would be sold next, not a
        price stored on the product: the laboratory sets it per batch, so two
        boxes on the same shelf can legitimately cost different amounts.
    '''
    sku: str
    description: str
    laboratory: str
    unit: str
    barcode: str | None = None
    min_stock: float
    requires_prescription: bool
    is_active: bool
    sin_activity_code: str | None = None
    sin_product_code: str | None = None
    sin_unit_code: int | None = None
    available_quantity: float = 0
    sale_price: float | None = None
    next_expiry: date | None = None
    below_minimum: bool = False
    ready_to_invoice: bool = Field(
        False, description = 'Tiene los tres códigos del SIN homologados.'
    )
    created_at: str | None = None
    updated_at: str | None = None


class ProductsResponse(BaseModel):
    '''
        The catalogue of one pharmacy.
    '''
    items: list[ProductOut]
    total: int


# --- lots --------------------------------------------------------------------

class LotOut(BaseModel):
    '''
        One batch received, with what is left of it.

        Cost and price travel together because both are set by the batch: the
        margin of a sale is only meaningful against the cost of the very units
        that left.
    '''
    lot_id: str
    sku: str
    lot_code: str | None = None
    expiry_date: date | None = None
    unit_cost: float
    sale_price: float
    quantity_received: float
    quantity_remaining: float
    purchase_id: str | None = None
    received_at: str


class LotsResponse(BaseModel):
    '''
        The lots of one SKU, in the order they will be sold.
    '''
    sku: str
    items: list[LotOut]
    available_quantity: float


class LotPricePatch(BaseModel):
    '''
        A re-priced batch. The cost is history and does not move; the shelf
        price does, and the pharmacy changes it without touching the note that
        brought the units in.
    '''
    sale_price: float = Field(..., gt = 0)


# --- purchase notes ----------------------------------------------------------

class PurchaseLineIn(BaseModel):
    '''
        One line of a nota de compra: a batch of one SKU.
    '''
    sku: str = Field(..., min_length = 1, max_length = 40)
    quantity: float = Field(..., gt = 0)
    unit_cost: float = Field(..., ge = 0)
    sale_price: float = Field(..., gt = 0)
    lot_code: str | None = Field(None, max_length = 60)
    expiry_date: date | None = None


class PurchaseNoteIn(BaseModel):
    '''
        Units coming in from a laboratory, importer or distributor.
    '''
    supplier_name: str = Field(..., min_length = 1, max_length = 200)
    supplier_document: str | None = Field(None, max_length = 40,
                                             description = 'NIT of the supplier.')
    invoice_number: str | None = Field(None, max_length = 60)
    invoice_date: date | None = None
    notes: str | None = Field(None, max_length = 500)
    lines: list[PurchaseLineIn] = Field(..., min_length = 1)


class PurchaseLineOut(PurchaseLineIn):
    '''
        A stored purchase line, carrying the lot it created.
    '''
    lot_id: str
    total_cost: float


class PurchaseNoteOut(BaseModel):
    '''
        A nota de compra as it was recorded.
    '''
    purchase_id: str
    number: str
    supplier_name: str
    supplier_document: str | None = None
    invoice_number: str | None = None
    invoice_date: date | None = None
    notes: str | None = None
    lines: list[PurchaseLineOut]
    total_cost: float
    created_by: str
    created_at: str


class PurchaseNotesResponse(BaseModel):
    '''
        Purchase notes of one pharmacy in a window.
    '''
    items: list[PurchaseNoteOut]
    total: int


# --- sale notes --------------------------------------------------------------

class Buyer(BaseModel):
    '''
        Who is buying. A pharmacy asks for it to invoice; with nothing given,
        the note is issued to the counter.
    '''
    name: str | None = Field(None, max_length = 200)
    document: str | None = Field(None, max_length = 40,
                                    description = 'NIT or CI, as the buyer gives it.')
    document_type: int | None = Field(
        None, ge = 1, le = 5,
        description = 'Código del tipo de documento según la paramétrica del '
                      'SIN. El anexo sólo fija el rango 1 a 5; qué número es '
                      'cada documento lo dice el catálogo que se sincroniza '
                      'con la autorización, y por eso no se nombra aquí.'
    )


class SaleLineIn(BaseModel):
    '''
        One product being sold. The price is not sent: it comes from the lots
        the units actually leave, which is what the shelf label says.
    '''
    sku: str = Field(..., min_length = 1, max_length = 40)
    quantity: float = Field(..., gt = 0)
    discount: float = Field(0, ge = 0,
                            description = 'Amount off this line, only when the '
                                          'pharmacy enables discounts.')


class SaleAllocation(BaseModel):
    '''
        The units of one line taken from one lot.

        A line spans several lots when the earliest-expiry batch does not cover
        it, and each batch may carry its own price — so the allocation, not the
        line, is what carries money and cost.
    '''
    lot_id: str
    lot_code: str | None = None
    expiry_date: date | None = None
    quantity: float
    unit_price: float
    unit_cost: float
    amount: float


class SaleLineOut(BaseModel):
    '''
        A sold line with what it cost the pharmacy and what it charged.
    '''
    sku: str
    description: str
    quantity: float
    discount: float
    allocations: list[SaleAllocation]
    subtotal: float = Field(..., description = 'Before the line discount.')
    total: float
    cost: float


class SaleNoteIn(BaseModel):
    '''
        A sale over the counter.
    '''
    buyer: Buyer = Field(default_factory = Buyer)
    payment_method: PaymentMethod = PaymentMethod.EFECTIVO
    notes: str | None = Field(None, max_length = 300)
    lines: list[SaleLineIn] = Field(..., min_length = 1)
    card_number: str | None = Field(
        None, max_length = 30,
        description = 'Card number, only when paying by card. It is MASKED on '
                      'the way in and only the masked form is ever stored: the '
                      'norm requires the middle digits zeroed, and the full '
                      'number is not ours to keep.'
    )


class SaleNoteOut(BaseModel):
    '''
        A sale note as it was issued and as it prints.
    '''
    sale_id: str
    number: str
    status: SaleStatus
    buyer: Buyer
    payment_method: PaymentMethod
    notes: str | None = None
    card_number: str | None = Field(
        None, description = 'Masked, when the sale was paid by card.'
    )
    lines: list[SaleLineOut]
    subtotal: float
    discount: float
    total: float
    cost: float
    margin: float = Field(..., description = 'total - cost, in currency.')
    created_by: str
    created_at: str
    cancelled_at: str | None = None
    cancelled_by: str | None = None
    cash_session_id: str | None = Field(
        None, description = 'The till the sale went into; empty on notes issued before tills.'
    )


class SaleNotesResponse(BaseModel):
    '''
        Sale notes of one pharmacy in a window, newest first.
    '''
    items: list[SaleNoteOut]
    total: int
    total_amount: float


# --- settings ----------------------------------------------------------------

class BillingSettings(BaseModel):
    '''
        What the pharmacy prints on its notes and what its counter allows.

        These are per-tenant parameters, not configuration of the service: two
        pharmacies on the same deployment number their notes independently and
        print their own name.
    '''
    trade_name: str = Field(..., min_length = 1, max_length = 200)
    document: str | None = Field(None, max_length = 40, description = 'NIT.')
    address: str | None = Field(None, max_length = 300)
    phone: str | None = Field(None, max_length = 40)
    municipality: str | None = Field(
        None, max_length = 25,
        description = 'Municipio o departamento que se imprime en la factura. '
                      'El XSD del SIN lo exige y ningún otro campo lo lleva.'
    )
    sale_series: str = Field('A', min_length = 1, max_length = 8)
    purchase_series: str = Field('C', min_length = 1, max_length = 8)
    discounts_enabled: bool = False
    ticket_width: TicketWidth = TicketWidth.MM_80
    ticket_footer: str | None = Field(None, max_length = 200)
    # --- Electronic invoicing ------------------------------------------------
    # Branch and point of sale are per-tenant and go INTO the CUF, which is why
    # they live here and not in the service configuration: two pharmacies on
    # the same deployment issue from different branches, and a CUF built with
    # the wrong one is a document the tax office rejects.
    branch: int = Field(
        0, ge = 0, le = 9999,
        description = 'Branch registered with the SIN; 0 is the head office.'
    )
    point_of_sale: int = Field(
        0, ge = 0, le = 9999,
        description = 'Point of sale registered with the SIN; 0 when there is none.'
    )
    # Phase II of the norm requires the buyer to be named on EVERY invoice,
    # whatever the amount. It is a flag and not a constant because a pharmacy
    # still issuing internal notes has to be able to work before it is
    # authorised, and because the day it is authorised nothing else changes.
    buyer_required: bool = Field(
        False,
        description = 'Refuse a sale with no buyer. Required once invoicing '
                      'electronically: the norm names the buyer on every '
                      'invoice, regardless of the amount.'
    )
    # --- Cash tills ------------------------------------------------------------
    # Per shop and not in the service configuration: each shop closes at its
    # own hour. Without it there is no end-of-day alert.
    cash_alert_time: time_type | None = Field(
        None,
        description = 'From this hour the screens warn about tills still open.'
    )


class SettingsResponse(BillingSettings):
    '''
        The settings plus the counters they drive.
    '''
    next_sale_number: int
    next_purchase_number: int


# --- counter dashboard -------------------------------------------------------

class ExpiringLot(BaseModel):
    '''
        A batch close enough to its expiry date to act on: return it to the
        laboratory, discount it, or push it at the counter.
    '''
    sku: str
    description: str
    lot_code: str | None = None
    expiry_date: date
    days_left: int
    quantity_remaining: float
    unit_cost: float
    value_at_cost: float


class LowStockProduct(BaseModel):
    '''
        A SKU at or under the minimum the pharmacy set for it.
    '''
    sku: str
    description: str
    available_quantity: float
    min_stock: float


class TopProduct(BaseModel):
    '''
        What sold most over the window, by amount charged.
    '''
    sku: str
    description: str
    quantity: float
    amount: float


class MethodTotal(BaseModel):
    '''
        What one payment method brought in.
    '''
    payment_method: PaymentMethod
    count: int
    total: float


class BillingDashboard(BaseModel):
    '''
        What the person behind the counter needs to see when they open the
        screen: what was sold, what it left, what is about to expire and what
        is about to run out.

        The window defaults to today because that is the question a till asks;
        the same numbers answer for any range.
    '''
    date_from: date
    date_to: date
    sales_count: int
    sales_amount: float
    sales_cost: float
    margin: float
    margin_percent: float | None = Field(
        None, description = 'Margin over the amount charged; None when nothing sold.'
    )
    average_ticket: float | None = None
    cancelled_count: int
    stock_value_at_cost: float
    expiry_alert_days: int
    expiring_soon: list[ExpiringLot]
    expired: list[ExpiringLot]
    low_stock: list[LowStockProduct]
    top_products: list[TopProduct]
    sales_by_method: list[MethodTotal] = []


# --- grouped arguments -------------------------------------------------------

class DateWindow(BaseModel):
    '''
        The days a listing covers. The two bounds are one concept: they travel
        together and neither is useful alone.
    '''
    date_from: date | None = None
    date_to: date | None = None


class LotQuery(BaseModel):
    '''
        Which SKU's batches are being asked for, and whether the exhausted ones
        count.
    '''
    sku: str = Field(..., min_length = 1, max_length = 40)
    only_available: bool = True


class ProductEdit(BaseModel):
    '''
        Which SKU is being edited and what changes about it.
    '''
    sku: str = Field(..., min_length = 1, max_length = 40)
    patch: ProductPatch


class LotEdit(BaseModel):
    '''
        Which batch is being re-priced and to what. The SKU and the lot address
        one row; neither means anything without the other.
    '''
    sku: str = Field(..., min_length = 1, max_length = 40)
    lot_id: str = Field(..., min_length = 1, max_length = 60)
    sale_price: float = Field(..., gt = 0)


# --- electronic invoicing ----------------------------------------------------

class InvoiceContext(BaseModel):
    """
        Everything the invoice XML needs that the sale itself does not carry.

        It is one object and not fifteen arguments because these travel
        together: they all come from the pharmacy's registration and from the
        codes the tax office hands back. Passing them loose is how a CUF ends
        up next to another invoice's CUFD.
    """
    issuer_document: str = Field(..., description = 'NIT of the issuing pharmacy.')
    trade_name: str = Field(..., min_length = 1, max_length = 200)
    municipality: str = Field(..., min_length = 1, max_length = 25)
    address: str = Field(..., min_length = 1, max_length = 500)
    phone: str | None = Field(None, max_length = 25)
    branch: int = Field(0, ge = 0, le = 9999)
    point_of_sale: int | None = Field(None, ge = 0, le = 9999)
    invoice_number: int = Field(..., ge = 1)
    cuf: str = Field(..., min_length = 1, max_length = 100)
    cufd: str = Field(
        ..., min_length = 1, max_length = 100,
        description = 'Code the tax office issues per day and point of sale.'
    )
    issued_at: str = Field(..., description = 'ISO 8601, as xs:dateTime wants it.')
    legend: str = Field(
        ..., min_length = 1, max_length = 200,
        description = 'Legend from the SIN catalogue. It changes with each '
                      'issue by law 453, so the caller picks it, not this.'
    )
    currency_code: int = Field(..., ge = 1, le = 154)
    exchange_rate: float = Field(..., gt = 0)
    cafc: str | None = Field(
        None, max_length = 50,
        description = 'Only on a contingency invoice; empty online.'
    )


class InvoiceLine(BaseModel):
    """
        One line as the invoice needs it: the sale's figures plus the three
        SIN codes, which live on the product and not on the stored line.

        They are demanded here rather than defaulted because an invoice with a
        plausible-looking product code is rejected by the tax office AFTER the
        sale is in the client's hands.
    """
    sku: str = Field(..., min_length = 1, max_length = 50)
    description: str = Field(..., min_length = 1, max_length = 500)
    quantity: float = Field(..., gt = 0)
    unit_price: float = Field(..., gt = 0)
    discount: float = Field(0, ge = 0)
    subtotal: float = Field(..., gt = 0)
    sin_activity_code: str | None = None
    sin_product_code: str | None = None
    sin_unit_code: int | None = None


class CuisResponse(BaseModel):
    """
        The CUIS the tax office issued, and when it stops being valid.

        It lasts a year, so it is asked for once and stored. Asking on every
        invoice would be a round trip to a service we do not control for a
        code that did not change.
    """
    cuis: str = Field(..., min_length = 1, max_length = 100)
    valid_until: str = Field(..., description = 'As the SIAT returns it.')


class CufdResponse(BaseModel):
    """
        The CUFD of one day and point of sale.

        `control_code` is what closes the CUF, so a CUFD of the wrong day
        produces a CUF the tax office rejects — which is why the day it is
        valid until travels with it.
    """
    cufd: str = Field(..., min_length = 1, max_length = 100)
    control_code: str = Field(..., min_length = 1, max_length = 100)
    address: str = Field(..., description = 'Address the SIAT has registered.')
    valid_until: str = Field(..., description = 'As the SIAT returns it.')


class SiatReceipt(BaseModel):
    """
        What the tax office answered about one document.

        `messages` keeps the SIN's own wording verbatim. It is the exception to
        the rule that this backend returns codes and not prose: these are not
        our messages to write, they carry the SIN's own code, and rewording
        them would lose the only text a person can use to argue with them.
    """
    accepted: bool
    reception_code: str | None = Field(
        None, description = 'Code to ask later whether it was validated.'
    )
    state: str | None = None
    messages: list[str] = Field(default_factory = list)
