'''
    SmartBilling → SmartDecisions' financial analysis (Rafael, 6-nov-2026).

    FINANCE keeps one amount per account and period, and a load of the same
    account and period replaces it; it also refuses to mix periodicities in
    one period, and the closing inventory is a month's. So what goes is the
    MONTH: every sale, cancellation, return or purchase rebuilds, from what
    BILLING stored, the totals of its month for every account of the bridge
    —zeros included, so a month whose sales were all cancelled is not left
    with the old figure— and sends them, with the opening and closing
    inventory of that month and of every month after it, which a change in a
    past month moves too.

    A cancelled sale never happened: it counts in no month. A return counts
    in the month of its credit note while the SIN holds it. The accounts are
    the shop's business values (`billing_parameters`).

    The closing inventory is rebuilt backwards from today's shelf: what the
    lots hold now, minus what came in after the month, plus what left after
    it for sales that stand, minus what came back after it for returns that
    stand. It needs no photo taken on the last day, and a past month reads
    exactly as it closed. It is valued as FINANCE values the purchases: a lot
    bought with an invoice is worth its cost without the VAT, which is a tax
    credit and not merchandise (seen live on 8-nov: the cost of sales came
    out short by exactly that VAT).
'''
from typing import Any

from boto3.resources.base import ServiceResource
from fastapi import Request

from core.environment import load_and_validate_env_vars
from core.utils import get_current_time_gmt, load_parameters
from models.billing import (
    LOTS_TABLE,
    PURCHASES_TABLE,
    PURCHASE_SORT_KEY,
    SALES_TABLE,
    SALE_SORT_KEY
)
from schemas.billing import ProductUnit, SaleStatus
from services.billing import (
    MONEY_DECIMALS,
    SortBounds,
    accepted_notes,
    date_window,
    products_by_sku,
    read_partition
)
from services.billing_bridge import lot_shares, merchandise_share, share_if_wanted

FINANCE_QUEUE_URL = load_and_validate_env_vars({'FINANCE_LIVE_QUEUE_URL': str})[
    'FINANCE_LIVE_QUEUE_URL']
LOADS_PATH = '/v1/finance/loads'

ACCOUNTS = load_parameters({
    'BILLING_FINANCE_SALES_INVOICED': str,
    'BILLING_FINANCE_SERVICES_INVOICED': str,
    'BILLING_FINANCE_SALES_UNINVOICED': str,
    'BILLING_FINANCE_SERVICES_UNINVOICED': str,
    'BILLING_FINANCE_RETURNS': str,
    'BILLING_FINANCE_PURCHASES_INVOICED': str,
    'BILLING_FINANCE_PURCHASES_UNINVOICED': str,
    'BILLING_FINANCE_OPENING_INVENTORY': str,
    'BILLING_FINANCE_CLOSING_INVENTORY': str,
    'BILLING_FINANCE_INVENTORY': str
})
# The accounts whose amounts carry the invoice's taxes: FINANCE asks it of them.
_INVOICED = frozenset({ACCOUNTS['BILLING_FINANCE_SALES_INVOICED'],
                       ACCOUNTS['BILLING_FINANCE_SERVICES_INVOICED'],
                       ACCOUNTS['BILLING_FINANCE_PURCHASES_INVOICED']})
# A credit note can be issued up to the 9th of the month after its sale, so
# the sales that may hold a month's returns start a month before it.
_RETURN_REACH_MONTHS = 1


def _month_after(month: str) -> str:
    '''
        The month that follows, as 'YYYY-MM'.

        Args:
            month (str): 'YYYY-MM'.

        Returns:
            str: The next month.
    '''
    year, number = int(month[:4]), int(month[5:7])
    return f'{year + number // 12:04d}-{number % 12 + 1:02d}'


def _month_before(month: str) -> str:
    '''
        The month that precedes, as 'YYYY-MM'.

        Args:
            month (str): 'YYYY-MM'.

        Returns:
            str: The previous month.
    '''
    year, number = int(month[:4]), int(month[5:7])
    return f'{year - 1:04d}-12' if number == 1 else f'{year:04d}-{number - 1:02d}'


def _documents(
    dynamodb_resource: ServiceResource,
    owner: str,
    table: tuple[str, str],
    since: str
) -> list[dict[str, Any]]:
    '''
        A shop's sales or purchases from the first day of a month on.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            table (tuple[str, str]): The table and its sort key.
            since (str): 'YYYY-MM', the first month read.

        Returns:
            list[dict[str, Any]]: The documents, oldest first.
    '''
    name, sort_key = table
    return read_partition(dynamodb_resource, name, owner, SortBounds(
        sort_key = sort_key, between = date_window(f'{since}-01', None)))


def _standing_sales(sales: list[dict[str, Any]]) -> list[dict[str, Any]]:
    '''
        The sales that happened: a cancelled one never did.

        Args:
            sales (list[dict[str, Any]]): Stored sales.

        Returns:
            list[dict[str, Any]]: The issued ones.
    '''
    return [sale for sale in sales if sale['status'] == SaleStatus.ISSUED.value]


def _sales_accounts(
    sales: list[dict[str, Any]],
    units: dict[str, str]
) -> dict[str, float]:
    '''
        The month's sales by account: with or without invoice, products or
        services.

        Args:
            sales (list[dict[str, Any]]): The month's standing sales.
            units (dict[str, str]): Each SKU's unit.

        Returns:
            dict[str, float]: Bolivianos per account.
    '''
    totals: dict[str, float] = {}
    for sale in sales:
        invoiced = bool(sale.get('invoice'))
        for line in sale['lines']:
            service = units.get(line['sku']) == ProductUnit.SERVICE.value
            code = ('BILLING_FINANCE_' + ('SERVICES' if service else 'SALES') +
                    ('_INVOICED' if invoiced else '_UNINVOICED'))
            totals[ACCOUNTS[code]] = totals.get(ACCOUNTS[code], 0.0) + float(line['total'])
    return totals


def _notes_in(
    sales: list[dict[str, Any]],
    month: str
) -> list[dict[str, Any]]:
    '''
        The credit notes the SIN holds that were issued in a month.

        Args:
            sales (list[dict[str, Any]]): The sales that may hold them.
            month (str): 'YYYY-MM'.

        Returns:
            list[dict[str, Any]]: The notes.
    '''
    return [note for sale in _standing_sales(sales) for note in accepted_notes(sale)
            if str(note['issued_at']).startswith(month)]


def _cost_of(
    lines: list[dict[str, Any]],
    lot_factor: dict[str, float]
) -> float:
    '''
        What the units of some lines cost, from the lots they left or reached.

        Args:
            lines (list[dict[str, Any]]): Sale or note lines with allocations.
            lot_factor (dict[str, float]): The share of each lot's cost that
                is merchandise.

        Returns:
            float: Bolivianos at cost.
    '''
    return sum(float(allocation['quantity']) * float(allocation['unit_cost']) *
               lot_factor.get(allocation['lot_id'], 1.0)
               for line in lines for allocation in line['allocations'])


def _closing_inventory(
    shelf: float,
    month: str,
    later: dict[str, Any]
) -> float:
    '''
        What the shelf held at cost when a month closed, rebuilt from today's.

        Args:
            shelf (float): Today's value of every lot at cost.
            month (str): 'YYYY-MM'.
            later (dict[str, Any]): The `sales` and `purchases` read, which
                include everything after the month, and each lot's `lot_factor`.

        Returns:
            float: Bolivianos at cost.
    '''
    after = _month_after(month)
    factor = later['lot_factor']
    bought = sum(float(purchase['total_cost']) * merchandise_share(purchase)
                 for purchase in later['purchases'] if purchase[PURCHASE_SORT_KEY] >= after)
    sales = _standing_sales(later['sales'])
    sold = sum(_cost_of(sale['lines'], factor) for sale in sales
               if sale[SALE_SORT_KEY] >= after)
    returned = sum(_cost_of(note['lines'], factor) for sale in sales
                   for note in accepted_notes(sale) if str(note['issued_at'])[:7] >= after)
    return shelf - bought + sold - returned


def _month_amounts(
    month: str,
    data: dict[str, Any],
    units: dict[str, str],
    shelf: float
) -> dict[str, float]:
    '''
        One month's amount for every account of the bridge.

        Args:
            month (str): 'YYYY-MM'.
            data (dict[str, Any]): The `sales` and `purchases` read, and
                each lot's `lot_factor`.
            units (dict[str, str]): Each SKU's unit.
            shelf (float): Today's value of every lot at cost.

        Returns:
            dict[str, float]: Bolivianos per account, zeros included.
    '''
    amounts = {code: 0.0 for code in ACCOUNTS.values()}
    amounts.update(_sales_accounts(
        [sale for sale in _standing_sales(data['sales']) if sale[SALE_SORT_KEY].startswith(month)],
        units))
    amounts[ACCOUNTS['BILLING_FINANCE_RETURNS']] = sum(
        float(note['amount_returned']) for note in _notes_in(data['sales'], month))
    for purchase in data['purchases']:
        if purchase[PURCHASE_SORT_KEY].startswith(month):
            code = ('BILLING_FINANCE_PURCHASES_INVOICED' if purchase.get('invoice_number')
                    else 'BILLING_FINANCE_PURCHASES_UNINVOICED')
            amounts[ACCOUNTS[code]] += float(purchase['total_cost'])
    closing = _closing_inventory(shelf, month, data)
    amounts[ACCOUNTS['BILLING_FINANCE_OPENING_INVENTORY']] = _closing_inventory(
        shelf, _month_before(month), data)
    amounts[ACCOUNTS['BILLING_FINANCE_CLOSING_INVENTORY']] = closing
    amounts[ACCOUNTS['BILLING_FINANCE_INVENTORY']] = closing
    return amounts


def finance_rows(
    dynamodb_resource: ServiceResource,
    owner: str,
    first_month: str
) -> list[dict[str, Any]]:
    '''
        Every account of the bridge for each month from `first_month` to the
        current one, as FINANCE's monthly rows.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            first_month (str): 'YYYY-MM', the month the change happened in.

        Returns:
            list[dict[str, Any]]: Rows in FINANCE's entries contract.
    '''
    current = get_current_time_gmt().date().isoformat()[:7]
    reach = first_month
    for _ in range(_RETURN_REACH_MONTHS):
        reach = _month_before(reach)
    # Every purchase, not only the recent ones: a lot on the shelf may come
    # from any of them, and its invoice decides what it is worth.
    purchases = read_partition(dynamodb_resource, PURCHASES_TABLE, owner)
    lots = read_partition(dynamodb_resource, LOTS_TABLE, owner)
    data = {'sales': _documents(dynamodb_resource, owner, (SALES_TABLE, SALE_SORT_KEY), reach),
            'purchases': purchases, 'lot_factor': lot_shares(lots, purchases)}
    units = {sku: product.get('unit') for sku, product in
             products_by_sku(dynamodb_resource, owner).items()}
    shelf = sum(float(lot['quantity_remaining']) * float(lot['unit_cost']) *
                data['lot_factor'][lot['lot_id']] for lot in lots)
    rows: list[dict[str, Any]] = []
    month = first_month
    while month <= current:
        rows += [{'date': month, 'periodicity': 'MONTHLY', 'account_code': code,
                  'amount': round(max(amount, 0.0), MONEY_DECIMALS),
                  'taxes_included': True if code in _INVOICED else None}
                 for code, amount in sorted(_month_amounts(month, data, units, shelf).items())]
        month = _month_after(month)
    return rows


def share_month(
    dynamodb_resource: ServiceResource,
    owner: str,
    day: str,
    request: Request | None
) -> None:
    '''
        Sends the financial figures of the month a change happened in, and of
        every month after it, when the shop wants it.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            day (str): When the change happened, ISO date or timestamp.
            request (Request | None): The incoming request, for the token.
    '''
    first_month = str(day)[:7]
    if not first_month or first_month > get_current_time_gmt().date().isoformat()[:7]:
        return
    share_if_wanted(dynamodb_resource, owner, request, (
        FINANCE_QUEUE_URL, LOADS_PATH,
        {'flow': 'PROCESSED', 'rows': finance_rows(dynamodb_resource, owner, first_month)}))
