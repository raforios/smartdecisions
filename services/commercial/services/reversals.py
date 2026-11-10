'''
    Cancellations and returns, known and analyzed on their own (Rafael,
    6-nov-2026), while the sales stay net.

    Each one is one record keyed by its kind and its id: the cancelled sale or
    the credit note. Reverting it writes the same record with the state
    REVERTED, so it stays on file and stops counting. The report reads what
    stands: by month at each month's close, by reason at today's rate, as
    every amount of the product is read (rule 2).
'''
from typing import Any

import pandas as pd
from boto3.resources.base import ServiceResource

from core.crud import find_item_by_key, put_items, query_by_partition
from core.environment import load_and_validate_env_vars
from core.logger_config import custom_logger as logger
from core.utils import get_current_time_gmt
from models.reversals import ReversalItem
from schemas.reversals import (
    ReversalMonth,
    ReversalReason,
    ReversalResponse,
    ReversalSchema,
    ReversalsReport,
    ReversalState
)
from services.analytics_utils import AMOUNT_DECIMALS
from services.commercial_utils import from_dynamo
from services.currency import money_row, money_sums, money_total, with_month_close_factors

REVERSALS_TABLE = load_and_validate_env_vars({'DYNAMODB_TABLE_NAME_COMMERCIAL_REVERSALS': str})[
    'DYNAMODB_TABLE_NAME_COMMERCIAL_REVERSALS']

# A reason the record does not give still groups: the report shows it as
# "no reason", never drops it.
_NO_REASON_CODE = 0
_NO_REASON = ''


def to_reversal_response(
    item: ReversalItem,
    dataset_id: str | None = None
) -> ReversalResponse:
    '''
        Turns a stored record into its DTO.

        Args:
            item (ReversalItem): Item as DynamoDB returned it.
            dataset_id (str | None): The dataset whose sale it set right.

        Returns:
            ReversalResponse: The record as the API publishes it.
    '''
    values = from_dynamo(dict(item))
    # The owner and the stored key's kind prefix are not published; the DTO
    # leaves out whatever it does not declare.
    return ReversalResponse.model_validate({
        **values, 'reversal_id': str(values['reversal_id']).split('#', 1)[1],
        'dataset_id': dataset_id
    })


def store_reversal(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    reversal: ReversalSchema
) -> ReversalItem:
    '''
        Records a cancellation or a return, or its new state when it is
        reverted or stands again; the day it was undone and the first day it
        was recorded are kept.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): The company.
            reversal (ReversalSchema): What was undone.

        Returns:
            ReversalItem: The record as stored.
    '''
    key = f'{reversal.kind.value}#{reversal.reversal_id}'
    previous = find_item_by_key(dynamodb_resource, REVERSALS_TABLE,
                                {'owner_email': owner_email, 'reversal_id': key})
    now = get_current_time_gmt().isoformat()
    item = ReversalItem(
        owner_email = owner_email,
        reversal_id = key,
        kind = reversal.kind.value,
        state = reversal.state.value,
        order_id = reversal.order_id,
        # The day it was undone; reverting it later does not move it.
        date = str(previous['date']) if previous else reversal.date.isoformat(),
        reason_code = reversal.reason_code,
        reason = reversal.reason,
        lines = [line.model_dump() for line in reversal.lines],
        quantity = round(sum(line.quantity for line in reversal.lines), AMOUNT_DECIMALS),
        amount = round(sum(line.amount for line in reversal.lines), AMOUNT_DECIMALS),
        created_at = str(previous['created_at']) if previous else now,
        updated_at = now
    )
    put_items(dynamodb_resource, REVERSALS_TABLE, [dict(item)])
    message = (f'{reversal.kind.value} {reversal.reversal_id} of {owner_email} recorded '
               f'{reversal.state.value}: {item["quantity"]} unit(s), {item["amount"]} Bs.')
    logger.info(message)
    return item


def list_reversals(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    window: dict[str, Any]
) -> list[ReversalItem]:
    '''
        The company's cancellations and returns in the window, newest first.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): The company.
            window (dict[str, Any]): `date_from` and `date_to`, either optional.

        Returns:
            list[ReversalItem]: The records, reverted ones included.
    '''
    items = query_by_partition(dynamodb_resource, REVERSALS_TABLE, 'owner_email', owner_email)
    date_from, date_to = window.get('date_from'), window.get('date_to')
    kept = [item for item in items
            if (not date_from or str(item['date']) >= str(date_from))
            and (not date_to or str(item['date']) <= str(date_to))]
    return sorted(kept, key = lambda item: (str(item['date']), str(item['updated_at'])),
                  reverse = True)


def build_report(
    items: list[ReversalItem],
    auth_token: str
) -> ReversalsReport:
    '''
        Totals by month and by reason over what stands, and every record.

        Args:
            items (list[ReversalItem]): The records of the window.
            auth_token (str): The caller's Authorization header, for QUOTES.

        Returns:
            ReversalsReport: The report.
    '''
    records = [to_reversal_response(item) for item in items]
    standing = [record for record in records if record.state is ReversalState.ACTIVE]
    if not standing:
        return ReversalsReport(reversals = records)
    frame = pd.DataFrame({
        'date': [record.date for record in standing],
        'month': [record.date[:7] for record in standing],
        'kind': [record.kind.value for record in standing],
        'reason_code': [record.reason_code or _NO_REASON_CODE for record in standing],
        'reason': [record.reason or _NO_REASON for record in standing],
        'quantity': [record.quantity for record in standing],
        'amount': [record.amount for record in standing]
    })
    frame = with_month_close_factors(frame, auth_token,
                                     get_current_time_gmt().date().isoformat())
    by_month = money_sums(frame, frame['amount'], ['month', 'kind'], by_month = True)
    counts = frame.groupby(['month', 'kind']).agg(count = ('amount', 'size'),
                                                  quantity = ('quantity', 'sum'))
    by_reason = money_sums(frame, frame['amount'], ['kind', 'reason_code', 'reason'])
    reason_counts = frame.groupby(['kind', 'reason_code', 'reason']).size()
    return ReversalsReport(
        count = len(standing),
        quantity = round(float(frame['quantity'].sum()), AMOUNT_DECIMALS),
        amount = money_row(money_total(frame, frame['amount'])),
        months = [ReversalMonth(month = month, kind = kind, count = int(counts.loc[(month, kind),
                                                                                  'count']),
                                quantity = round(float(counts.loc[(month, kind), 'quantity']),
                                                 AMOUNT_DECIMALS),
                                amount = money_row(sums))
                  for (month, kind), sums in by_month.iterrows()],
        reasons = sorted(
            (ReversalReason(kind = kind, reason_code = code or None, reason = reason or None,
                            count = int(reason_counts.loc[(kind, code, reason)]),
                            amount = money_row(sums))
             for (kind, code, reason), sums in by_reason.iterrows()),
            key = lambda row: -row.amount.bob),
        reversals = records
    )
