'''
    Pharmacy billing: the DynamoDB items.

    Five tables, all partitioned by owner — the pharmacy. The owner is part of
    every key and never a filter applied afterwards: a pharmacy that could read
    another's shelf would be reading its margins.

    | Table                | Partition | Sort                  |
    |----------------------|-----------|-----------------------|
    | pharmacy_products    | owner     | sku                   |
    | pharmacy_lots        | owner     | lot_key = sku#lot_id  |
    | pharmacy_sales       | owner     | sale_id (time-sorted) |
    | pharmacy_purchases   | owner     | purchase_id           |
    | pharmacy_settings    | owner     | setting_key           |

    `lot_key` puts every lot of one SKU together, so the batches to sell next
    come back with a single `begins_with` query instead of a scan. The sale and
    purchase identifiers start with the timestamp, which is what makes a date
    window a bounded Query on the sort key rather than a filter over the table.
'''
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.environment import load_and_validate_env_vars

ENV_VARS = load_and_validate_env_vars(
    {
        'DYNAMODB_TABLE_NAME_PHARMACY_PRODUCTS': str,
        'DYNAMODB_TABLE_NAME_PHARMACY_LOTS': str,
        'DYNAMODB_TABLE_NAME_PHARMACY_SALES': str,
        'DYNAMODB_TABLE_NAME_PHARMACY_PURCHASES': str,
        'DYNAMODB_TABLE_NAME_PHARMACY_SETTINGS': str
    }
)

PRODUCTS_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_PHARMACY_PRODUCTS']
LOTS_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_PHARMACY_LOTS']
SALES_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_PHARMACY_SALES']
PURCHASES_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_PHARMACY_PURCHASES']
SETTINGS_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_PHARMACY_SETTINGS']

OWNER_KEY = 'owner'
PRODUCT_SORT_KEY = 'sku'
LOT_SORT_KEY = 'lot_key'
SALE_SORT_KEY = 'sale_id'
PURCHASE_SORT_KEY = 'purchase_id'
SETTING_SORT_KEY = 'setting_key'

# The single settings row of a pharmacy, and the two counters that number its
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
        A SKU in one pharmacy's catalogue.
    '''
    owner: str
    sku: str
    description: str
    laboratory: str
    unit: str = 'UND'
    barcode: Optional[str] = None
    min_stock: float = 0
    requires_prescription: bool = False
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


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
    lot_code: Optional[str] = None
    expiry_date: Optional[str] = None
    purchase_id: Optional[str] = None

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
    lines: List[Dict[str, Any]]
    subtotal: float
    discount: float
    total: float
    cost: float
    created_by: str
    created_at: str
    buyer: Dict[str, Any] = field(default_factory = dict)
    notes: Optional[str] = None
    cancelled_at: Optional[str] = None
    cancelled_by: Optional[str] = None


@dataclass
class PurchaseItem:
    '''
        A nota de compra: what a supplier delivered, and the lots it created.
    '''
    owner: str
    purchase_id: str
    number: str
    supplier_name: str
    lines: List[Dict[str, Any]]
    total_cost: float
    created_by: str
    created_at: str
    supplier_document: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    notes: Optional[str] = None
