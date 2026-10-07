'''
    Seller master model for DynamoDB.
'''
from typing import TypedDict


class SellerItem(TypedDict, total = False):
    '''
        Python model representing one seller of the master in DynamoDB.

        Table: ingest_sellers
        Partition Key: owner_email (String) — the account that owns the data.
        Sort Key: id (String) — the seller as the owner's files write it, so a
                  reload recognises the same seller.
    '''
    owner_email: str
    id: str
    name: str
    user_email: str | None
    source: str
    created_at: str
    updated_at: str
