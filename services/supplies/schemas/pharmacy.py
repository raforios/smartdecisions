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
from datetime import date
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class PharmacyError(str, Enum):
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


class PaymentMethod(str, Enum):
    '''
        How the buyer paid. A pharmacy counter takes these three.
    '''
    EFECTIVO = 'EFECTIVO'
    QR = 'QR'
    TARJETA = 'TARJETA'


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
    barcode: Optional[str] = Field(None, max_length = 60)
    min_stock: float = Field(0, ge = 0)
    requires_prescription: bool = False
    is_active: bool = True


class ProductPatch(BaseModel):
    '''
        What may change about a SKU after it was registered. The SKU itself
        never does: it is the key the lots and the sold lines point at.
    '''
    description: Optional[str] = Field(None, min_length = 1, max_length = 300)
    laboratory: Optional[str] = Field(None, min_length = 1, max_length = 150)
    unit: Optional[str] = Field(None, min_length = 1, max_length = 20)
    barcode: Optional[str] = Field(None, max_length = 60)
    min_stock: Optional[float] = Field(None, ge = 0)
    requires_prescription: Optional[bool] = None
    is_active: Optional[bool] = None


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
    barcode: Optional[str] = None
    min_stock: float
    requires_prescription: bool
    is_active: bool
    available_quantity: float = 0
    sale_price: Optional[float] = None
    next_expiry: Optional[date] = None
    below_minimum: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ProductsResponse(BaseModel):
    '''
        The catalogue of one pharmacy.
    '''
    items: List[ProductOut]
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
    lot_code: Optional[str] = None
    expiry_date: Optional[date] = None
    unit_cost: float
    sale_price: float
    quantity_received: float
    quantity_remaining: float
    purchase_id: Optional[str] = None
    received_at: str


class LotsResponse(BaseModel):
    '''
        The lots of one SKU, in the order they will be sold.
    '''
    sku: str
    items: List[LotOut]
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
    lot_code: Optional[str] = Field(None, max_length = 60)
    expiry_date: Optional[date] = None


class PurchaseNoteIn(BaseModel):
    '''
        Units coming in from a laboratory, importer or distributor.
    '''
    supplier_name: str = Field(..., min_length = 1, max_length = 200)
    supplier_document: Optional[str] = Field(None, max_length = 40,
                                             description = 'NIT of the supplier.')
    invoice_number: Optional[str] = Field(None, max_length = 60)
    invoice_date: Optional[date] = None
    notes: Optional[str] = Field(None, max_length = 500)
    lines: List[PurchaseLineIn] = Field(..., min_length = 1)


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
    supplier_document: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[date] = None
    notes: Optional[str] = None
    lines: List[PurchaseLineOut]
    total_cost: float
    created_by: str
    created_at: str


class PurchaseNotesResponse(BaseModel):
    '''
        Purchase notes of one pharmacy in a window.
    '''
    items: List[PurchaseNoteOut]
    total: int


# --- sale notes --------------------------------------------------------------

class Buyer(BaseModel):
    '''
        Who is buying. A pharmacy asks for it to invoice; with nothing given,
        the note is issued to the counter.
    '''
    name: Optional[str] = Field(None, max_length = 200)
    document: Optional[str] = Field(None, max_length = 40,
                                    description = 'NIT or CI, as the buyer gives it.')


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
    lot_code: Optional[str] = None
    expiry_date: Optional[date] = None
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
    allocations: List[SaleAllocation]
    subtotal: float = Field(..., description = 'Before the line discount.')
    total: float
    cost: float


class SaleNoteIn(BaseModel):
    '''
        A sale over the counter.
    '''
    buyer: Buyer = Field(default_factory = Buyer)
    payment_method: PaymentMethod = PaymentMethod.EFECTIVO
    notes: Optional[str] = Field(None, max_length = 300)
    lines: List[SaleLineIn] = Field(..., min_length = 1)


class SaleNoteOut(BaseModel):
    '''
        A sale note as it was issued and as it prints.
    '''
    sale_id: str
    number: str
    status: SaleStatus
    buyer: Buyer
    payment_method: PaymentMethod
    notes: Optional[str] = None
    lines: List[SaleLineOut]
    subtotal: float
    discount: float
    total: float
    cost: float
    margin: float = Field(..., description = 'total - cost, in currency.')
    created_by: str
    created_at: str
    cancelled_at: Optional[str] = None
    cancelled_by: Optional[str] = None


class SaleNotesResponse(BaseModel):
    '''
        Sale notes of one pharmacy in a window, newest first.
    '''
    items: List[SaleNoteOut]
    total: int
    total_amount: float


# --- settings ----------------------------------------------------------------

class PharmacySettings(BaseModel):
    '''
        What the pharmacy prints on its notes and what its counter allows.

        These are per-tenant parameters, not configuration of the service: two
        pharmacies on the same deployment number their notes independently and
        print their own name.
    '''
    trade_name: str = Field(..., min_length = 1, max_length = 200)
    document: Optional[str] = Field(None, max_length = 40, description = 'NIT.')
    address: Optional[str] = Field(None, max_length = 300)
    phone: Optional[str] = Field(None, max_length = 40)
    sale_series: str = Field('A', min_length = 1, max_length = 8)
    purchase_series: str = Field('C', min_length = 1, max_length = 8)
    discounts_enabled: bool = False
    ticket_width: TicketWidth = TicketWidth.MM_80
    ticket_footer: Optional[str] = Field(None, max_length = 200)


class SettingsResponse(PharmacySettings):
    '''
        The settings plus the counters they drive.
    '''
    next_sale_number: int
    next_purchase_number: int
