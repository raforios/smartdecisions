'''
    Pharmacy billing: what the counter needs to see.

    The old warehouse dashboard counted requisitions, which this product does
    not have. What a pharmacy asks instead is four things: what did I sell,
    what did it leave me, what is about to expire, and what am I about to run
    out of.

    Every figure comes from what is already stored — the notes and the lots —
    so nothing here has its own truth to keep in sync.
'''
from datetime import date as date_type, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from boto3.resources.base import ServiceResource

from models.pharmacy import LOTS_TABLE
from schemas.pharmacy import (
    ExpiringLot,
    LowStockProduct,
    PharmacyDashboard,
    SaleStatus,
    TopProduct
)
from services.environment import load_and_validate_env_vars
from services.pharmacy import products_by_sku, read_partition
from services.pharmacy_sales import list_sales

ENV_VARS = load_and_validate_env_vars({'PHARMACY_EXPIRY_ALERT_DAYS': int})
EXPIRY_ALERT_DAYS = ENV_VARS['PHARMACY_EXPIRY_ALERT_DAYS']

MONEY_DECIMALS = 2
# How many rows each list carries. A counter screen is read at a glance; the
# full lists live in their own sections.
TOP_ROWS = 5
LIST_ROWS = 10


def dashboard(
    dynamodb_resource: ServiceResource,
    owner: str,
    date_from: Optional[date_type] = None,
    date_to: Optional[date_type] = None,
    today: Optional[date_type] = None
) -> PharmacyDashboard:
    '''
        The counter summary for a window, today by default.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The pharmacy.
            date_from (date | None): First day; today when absent.
            date_to (date | None): Last day; today when absent.
            today (date | None): The day to measure expiries against; the real
                one when absent. Injected so the tests are not a calendar.

        Returns:
            PharmacyDashboard: Sales, margin, expiries and low stock.
    '''
    reference = today or date_type.today()
    start = date_from or reference
    end = date_to or reference

    sales = list_sales(dynamodb_resource, owner, start.isoformat(), end.isoformat())
    issued = [note for note in sales.items if note.status == SaleStatus.ISSUED]

    products = products_by_sku(dynamodb_resource, owner)
    lots = read_partition(dynamodb_resource, LOTS_TABLE, owner)
    expiring, expired = _expiry_lists(lots, products, reference)

    return PharmacyDashboard(
        date_from = start,
        date_to = end,
        cancelled_count = len(sales.items) - len(issued),
        stock_value_at_cost = _stock_value(lots),
        expiry_alert_days = EXPIRY_ALERT_DAYS,
        expiring_soon = expiring,
        expired = expired,
        low_stock = _low_stock(lots, products),
        top_products = _top_products(issued),
        **_money(issued)
    )


def _money(issued: List[Any]) -> Dict[str, Any]:
    '''
        What the window charged and what it left.

        Args:
            issued (List[SaleNoteOut]): The notes that were not cancelled.

        Returns:
            Dict[str, Any]: count, amount, cost, margin, percentage and ticket.
    '''
    amount = round(sum(note.total for note in issued), MONEY_DECIMALS)
    cost = round(sum(note.cost for note in issued), MONEY_DECIMALS)
    margin = round(amount - cost, MONEY_DECIMALS)
    return {
        'sales_count': len(issued),
        'sales_amount': amount,
        'sales_cost': cost,
        'margin': margin,
        'margin_percent': round(margin / amount * 100, MONEY_DECIMALS) if amount else None,
        'average_ticket': round(amount / len(issued), MONEY_DECIMALS) if issued else None
    }


def _stock_value(lots: List[Dict[str, Any]]) -> float:
    '''
        What the shelf is worth at what it cost.

        Args:
            lots (List[Dict[str, Any]]): Every batch of the pharmacy.

        Returns:
            float: Units left times their own cost, summed.
    '''
    return round(sum(lot['quantity_remaining'] * lot['unit_cost']
                     for lot in lots if lot.get('quantity_remaining', 0) > 0),
                 MONEY_DECIMALS)


def _expiry_lists(
    lots: List[Dict[str, Any]],
    products: Dict[str, Dict[str, Any]],
    reference: date_type
) -> Tuple[List[ExpiringLot], List[ExpiringLot]]:
    '''
        The batches about to expire and the ones already expired.

        They are reported apart because they call for different actions: one
        can still be sold or returned, the other has to leave the shelf.

        Args:
            lots (List[Dict[str, Any]]): Every batch of the pharmacy.
            products (Dict[str, Dict[str, Any]]): The catalogue by SKU.
            reference (date): The day to measure against.

        Returns:
            Tuple[List[ExpiringLot], List[ExpiringLot]]: (expiring, expired).
    '''
    horizon = reference + timedelta(days = EXPIRY_ALERT_DAYS)
    expiring: List[ExpiringLot] = []
    expired: List[ExpiringLot] = []

    for lot in lots:
        if lot.get('quantity_remaining', 0) <= 0 or not lot.get('expiry_date'):
            continue
        expiry = datetime.fromisoformat(lot['expiry_date']).date()
        if expiry > horizon:
            continue
        row = ExpiringLot(
            sku = lot['sku'],
            description = products.get(lot['sku'], {}).get('description', lot['sku']),
            lot_code = lot.get('lot_code'),
            expiry_date = expiry,
            days_left = (expiry - reference).days,
            quantity_remaining = lot['quantity_remaining'],
            unit_cost = lot['unit_cost'],
            value_at_cost = round(lot['quantity_remaining'] * lot['unit_cost'],
                                  MONEY_DECIMALS)
        )
        (expired if expiry < reference else expiring).append(row)

    expiring.sort(key = lambda row: row.expiry_date)
    expired.sort(key = lambda row: row.expiry_date)
    return expiring[:LIST_ROWS], expired[:LIST_ROWS]


def _low_stock(
    lots: List[Dict[str, Any]],
    products: Dict[str, Dict[str, Any]]
) -> List[LowStockProduct]:
    '''
        The SKUs at or under their own minimum.

        A product with a minimum of zero is never low: the pharmacy said it
        does not care to keep it in stock.

        Args:
            lots (List[Dict[str, Any]]): Every batch of the pharmacy.
            products (Dict[str, Dict[str, Any]]): The catalogue by SKU.

        Returns:
            List[LowStockProduct]: Shortest first.
    '''
    available: Dict[str, float] = {}
    for lot in lots:
        if lot.get('quantity_remaining', 0) > 0:
            available[lot['sku']] = available.get(lot['sku'], 0) + lot['quantity_remaining']

    rows = [
        LowStockProduct(
            sku = sku, description = product['description'],
            available_quantity = available.get(sku, 0),
            min_stock = product.get('min_stock', 0)
        )
        for sku, product in products.items()
        if product.get('is_active', True) and product.get('min_stock', 0) > 0
        and available.get(sku, 0) <= product['min_stock']
    ]
    rows.sort(key = lambda row: row.available_quantity)
    return rows[:LIST_ROWS]


def _top_products(issued: List[Any]) -> List[TopProduct]:
    '''
        What sold most over the window, by amount charged.

        Args:
            issued (List[SaleNoteOut]): The notes that were not cancelled.

        Returns:
            List[TopProduct]: Highest amount first.
    '''
    grouped: Dict[str, Dict[str, Any]] = {}
    for note in issued:
        for line in note.lines:
            row = grouped.setdefault(line.sku, {
                'description': line.description, 'quantity': 0.0, 'amount': 0.0
            })
            row['quantity'] += line.quantity
            row['amount'] += line.total

    rows = [
        TopProduct(sku = sku, description = row['description'],
                   quantity = row['quantity'],
                   amount = round(row['amount'], MONEY_DECIMALS))
        for sku, row in grouped.items()
    ]
    rows.sort(key = lambda row: row.amount, reverse = True)
    return rows[:TOP_ROWS]
