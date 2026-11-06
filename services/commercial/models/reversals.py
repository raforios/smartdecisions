'''
    Cancellations and returns model for DynamoDB.
'''
from typing import TypedDict


class ReversalItem(TypedDict, total = False):
    '''
        One cancellation or return in DynamoDB.

        Table: commercial_reversals
        Partition Key: owner_email (String) — the account that owns the data.
        Sort Key: reversal_id (String) — "{kind}#{id}": the cancelled sale or
                  the credit note, so reverting one rewrites the same item.

        `lines` holds what was undone, product by product; `quantity` and
        `amount` (bolivianos) are their sums, kept for the report.
    '''
    owner_email: str
    reversal_id: str
    kind: str
    state: str
    order_id: str
    date: str
    reason_code: int | None
    reason: str | None
    lines: list[dict]
    quantity: float
    amount: float
    created_at: str
    updated_at: str
