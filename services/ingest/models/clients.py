'''
    Client master model for DynamoDB.
'''
from typing import Optional, TypedDict


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
    tax_id: Optional[str]
    client_type: Optional[str]
    channel: Optional[str]
    zone: Optional[str]
    city: Optional[str]
    region: Optional[str]
    address: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    phone: Optional[str]
    contact: Optional[str]
    seller: Optional[str]
    credit_limit: Optional[float]
    cluster: Optional[str]
    supervisor: Optional[str]
    market: Optional[str]
    source: str
    created_at: str
    updated_at: str
