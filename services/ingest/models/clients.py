'''
    Client master model for DynamoDB.
'''
from typing import TypedDict


class ClientItem(TypedDict, total = False):
    '''
        Python model representing one client of the master in DynamoDB.

        Table: ingest_clients
        Partition Key: owner_email (String) — the account that owns the data.
        Sort Key: id (String) — the client code as the owner's own system
                  writes it, so a reload recognises the same client.

        Source values, kept because they change how much a field can be
        trusted: 'FILE' (came in an uploaded workbook), 'API' (pushed by the
        owner's ERP) and 'FIELD' (a seller registered it from the street).
    '''
    owner_email: str
    id: str
    name: str
    tax_id: str | None
    client_type: str | None
    channel: str | None
    zone: str | None
    city: str | None
    region: str | None
    address: str | None
    latitude: float | None
    longitude: float | None
    phone: str | None
    contact: str | None
    seller: str | None
    credit_limit: float | None
    cluster: str | None
    supervisor: str | None
    market: str | None
    source: str
    created_at: str
    updated_at: str
