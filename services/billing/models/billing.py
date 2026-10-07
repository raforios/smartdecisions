'''
    Billing: the DynamoDB items.

    Seven tables, all partitioned by owner — the shop. The owner is part of every
    key and never a filter applied afterwards: a shop that could read
    another's shelf would be reading its margins.

    | Table                | Partition | Sort                  |
    |----------------------|-----------|-----------------------|
    | billing_products     | owner     | sku                   |
    | billing_lots         | owner     | lot_key = sku#lot_id  |
    | billing_sales        | owner     | sale_id (time-sorted) |
    | billing_purchases    | owner     | purchase_id           |
    | billing_settings     | owner     | setting_key           |
    | billing_cash_sessions| owner     | session_id (time-sorted) |
    | billing_cash_movements| owner    | movement_key = session_id#movement_id |

    `lot_key` puts every lot of one SKU together, so the batches to sell next
    come back with a single `begins_with` query instead of a scan. The sale and
    purchase identifiers start with the timestamp, which is what makes a date
    window a bounded Query on the sort key rather than a filter over the table.
'''
from dataclasses import dataclass, field
from typing import Any

from services.environment import load_and_validate_env_vars

ENV_VARS = load_and_validate_env_vars(
    {
        'DYNAMODB_TABLE_NAME_BILLING_PRODUCTS': str,
        'DYNAMODB_TABLE_NAME_BILLING_LOTS': str,
        'DYNAMODB_TABLE_NAME_BILLING_SALES': str,
        'DYNAMODB_TABLE_NAME_BILLING_PURCHASES': str,
        'DYNAMODB_TABLE_NAME_BILLING_SETTINGS': str,
        'DYNAMODB_TABLE_NAME_BILLING_CASH_SESSIONS': str,
        'DYNAMODB_TABLE_NAME_BILLING_CASH_MOVEMENTS': str
    }
)

PRODUCTS_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_BILLING_PRODUCTS']
LOTS_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_BILLING_LOTS']
SALES_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_BILLING_SALES']
PURCHASES_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_BILLING_PURCHASES']
SETTINGS_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_BILLING_SETTINGS']
CASH_SESSIONS_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_BILLING_CASH_SESSIONS']
CASH_MOVEMENTS_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_BILLING_CASH_MOVEMENTS']

OWNER_KEY = 'owner'
PRODUCT_SORT_KEY = 'sku'
LOT_SORT_KEY = 'lot_key'
SALE_SORT_KEY = 'sale_id'
PURCHASE_SORT_KEY = 'purchase_id'
SETTING_SORT_KEY = 'setting_key'
CASH_SESSION_SORT_KEY = 'session_id'
CASH_MOVEMENT_SORT_KEY = 'movement_key'

# The single settings row of a shop, and the two counters that number its
# documents. Counters live beside the settings because they are the same kind
# of thing: per-tenant parameters, read and written by the same owner.
CONFIG_KEY = 'config'
SALE_COUNTER_KEY = 'counter#sale'
PURCHASE_COUNTER_KEY = 'counter#purchase'


def lot_key(
    sku: str,
    lot_id: str
) -> str:
    '''
        The sort key of a lot.

        Args:
            sku (str): Product the lot belongs to.
            lot_id (str): Identifier of the lot.

        Returns:
            str: "sku#lot_id".
    '''
    return f'{sku}#{lot_id}'


@dataclass
class ProductItem:
    '''
        A SKU in one shop's catalogue.
    '''
    owner: str
    sku: str
    description: str
    laboratory: str
    unit: str = 'UND'
    barcode: str | None = None
    min_stock: float = 0
    requires_prescription: bool = False
    is_active: bool = True
    # Homologation before the SIN: economic activity, product code and unit of
    # measure, each from its catalogue. Empty until the pharmacy fills them in;
    # without them the product cannot travel on an electronic invoice.
    sin_activity_code: str | None = None
    sin_product_code: str | None = None
    sin_unit_code: int | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class LotItem:
    '''
        One batch of one SKU, with the cost it came in at and the price it
        sells at. Both belong to the batch: the laboratory sets them per
        purchase, so the same product on the same shelf can carry two prices.
    '''
    owner: str
    sku: str
    lot_id: str
    unit_cost: float
    sale_price: float
    quantity_received: float
    quantity_remaining: float
    received_at: str
    lot_code: str | None = None
    expiry_date: str | None = None
    purchase_id: str | None = None

    @property
    def sort_key(self) -> str:
        '''
            The sort key this lot is stored under.

            Returns:
                str: "sku#lot_id".
        '''
        return lot_key(self.sku, self.lot_id)


@dataclass
class SaleItem:
    '''
        A sale note. The lines carry their allocations — which lot each unit
        left — so cancelling the note returns exactly those units to exactly
        those batches, and the margin is measured against what they cost.
    '''
    owner: str
    sale_id: str
    number: str
    status: str
    payment_method: str
    lines: list[dict[str, Any]]
    subtotal: float
    discount: float
    total: float
    cost: float
    created_by: str
    created_at: str
    buyer: dict[str, Any] = field(default_factory = dict)
    notes: str | None = None
    # Already masked when it gets here. The full number is never written: the
    # norm requires the middle digits zeroed, and a number we do not hold is a
    # number that cannot leak.
    card_number: str | None = None
    cancelled_at: str | None = None
    cancelled_by: str | None = None
    # The till the sale went into. Empty on notes issued before tills existed.
    cash_session_id: str | None = None


@dataclass
class PurchaseItem:
    '''
        A nota de compra: what a supplier delivered, and the lots it created.
    '''
    owner: str
    purchase_id: str
    number: str
    supplier_name: str
    lines: list[dict[str, Any]]
    total_cost: float
    created_by: str
    created_at: str
    supplier_document: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    notes: str | None = None


def movement_key(
    session_id: str,
    movement_id: str
) -> str:
    '''
        The sort key of a till movement.

        Args:
            session_id (str): The till.
            movement_id (str): The movement.

        Returns:
            str: "session_id#movement_id", so a whole shift is one begins_with.
    '''
    return f'{session_id}#{movement_id}'


@dataclass
class CashSessionItem:
    '''
        A till: one user's shift, for one day. The identifier starts with the
        opening time, so the tills of a day are a bounded Query.
    '''
    owner: str
    session_id: str
    user_email: str
    status: str
    business_day: str
    opened_at: str
    opening_cash: float
    closed_at: str | None = None
    closed_by: str | None = None
    counted_cash: float | None = None
    expected_cash: float | None = None
    difference: float | None = None
    note: str | None = None


@dataclass
class CashMovementItem:
    '''
        Cash that left a till. Never deleted: a cancellation records who and
        when, and the movement stops counting.
    '''
    owner: str
    movement_key: str
    session_id: str
    movement_id: str
    expense_type: str
    amount: float
    concept: str
    status: str
    created_by: str
    created_at: str
    purchase_id: str | None = None
    cancelled_by: str | None = None
    cancelled_at: str | None = None
