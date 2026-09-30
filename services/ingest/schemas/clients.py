'''
    Pydantic V2 DTOs for the client master.

    What describes WHO buys is stated once in the master and not repeated on
    every sales line. The column contract itself lives in schemas/ingest.py
    (CLIENT_COLUMNS) next to its siblings; this module holds the HTTP envelope
    of the two channels that feed it — the API the owner's ERP calls and the
    registration a seller makes from the street — plus the reading side.
'''
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class ClientError(str, Enum):
    '''
        Why a client request could not be served.

        A stable code, never a sentence: the wording belongs to whoever renders
        it. Same reasoning as IngestError.
    '''
    CLIENT_NOT_FOUND = 'CLIENT_NOT_FOUND'
    EMPTY_CLIENT_LOAD = 'EMPTY_CLIENT_LOAD'
    DUPLICATE_CLIENT_ID = 'DUPLICATE_CLIENT_ID'


class ClientSource(str, Enum):
    '''
        Where a client record came from. It is kept because it says how much a
        field can be trusted: coordinates typed at a desk and coordinates read
        by a phone standing at the door are not the same evidence.
    '''
    FILE = 'FILE'
    API = 'API'
    FIELD = 'FIELD'


class ClientBase(BaseModel):
    '''
        The attributes of a client, all optional but the identity.
    '''
    name: Optional[str] = Field(None, max_length = 150)
    tax_id: Optional[str] = Field(None, max_length = 40)
    client_type: Optional[str] = Field(None, max_length = 64)
    channel: Optional[str] = Field(None, max_length = 64)
    zone: Optional[str] = Field(None, max_length = 100)
    city: Optional[str] = Field(None, max_length = 100)
    region: Optional[str] = Field(None, max_length = 100)
    address: Optional[str] = Field(None, max_length = 255)
    latitude: Optional[float] = Field(None, ge = -90.0, le = 90.0)
    longitude: Optional[float] = Field(None, ge = -180.0, le = 180.0)
    phone: Optional[str] = Field(None, max_length = 40)
    contact: Optional[str] = Field(None, max_length = 150)
    seller: Optional[str] = Field(None, max_length = 128)
    credit_limit: Optional[float] = Field(None, ge = 0.0)
    # The commercial hierarchy. Declared in the file contract since Fase H but
    # missing here, so a clients upload carrying them lost them in silence —
    # the master could not hold what the validator accepted.
    cluster: Optional[str] = Field(None, max_length = 40)
    supervisor: Optional[str] = Field(None, max_length = 128)
    market: Optional[str] = Field(None, max_length = 100)


class ClientUpsertSchema(ClientBase):
    '''
        One client as the owner's ERP pushes it, or as a seller registers it.

        `name` is required here although the master allows it empty: a record
        created on purpose names the client, while one derived from a sales
        line may only have the code.
    '''
    id: str = Field(..., min_length = 1, max_length = 64,
                    description = 'Client code in the owner\'s own system.')
    name: str = Field(..., min_length = 1, max_length = 150)


class ClientBulkUpsertSchema(BaseModel):
    '''
        A batch of clients pushed in one call.
    '''
    clients: List[ClientUpsertSchema] = Field(..., min_length = 1)


class CallerClaims(BaseModel):
    """
        What the token says about the caller.

        The owner key and the caller are not the same thing: a SELLER writes
        into their company's master, but the record has to remember which
        person walked to that door.
    """
    email: str
    role: Optional[str] = None
    client: Optional[str] = None


class FieldClientSchema(BaseModel):
    """
        A client registered from the street.

        The coordinates are required here and optional everywhere else, which
        is the whole point of this door: the record is created by somebody
        standing at the shop, and that reading beats any spreadsheet.

        `id` is optional because the seller often does not know the code the
        ERP uses — and may be registering a client the ERP has never seen.
    """
    id: Optional[str] = Field(
        None, min_length = 1, max_length = 64,
        description = 'Client code in the owner\'s system, when the seller knows it.'
    )
    name: str = Field(..., min_length = 1, max_length = 150)
    latitude: float = Field(..., ge = -90.0, le = 90.0)
    longitude: float = Field(..., ge = -180.0, le = 180.0)
    address: Optional[str] = Field(None, max_length = 255)
    zone: Optional[str] = Field(None, max_length = 100)
    city: Optional[str] = Field(None, max_length = 100)
    client_type: Optional[str] = Field(None, max_length = 64)
    phone: Optional[str] = Field(None, max_length = 40)
    contact: Optional[str] = Field(None, max_length = 150)


class ClientUpdateSchema(ClientBase):
    '''
        A correction to a client already in the master. Unlike a load, this
        one OVERWRITES what it names: it is an explicit decision, not the side
        effect of re-reading a file.
    '''


class ClientResponseSchema(ClientBase):
    '''
        One client of the master as it is stored.
    '''
    id: str
    source: ClientSource
    created_at: str
    updated_at: str


class ClientListResponseSchema(BaseModel):
    '''
        The owner's clients.
    '''
    clients: List[ClientResponseSchema]
    total: int = Field(..., ge = 0)
    with_coordinates: int = Field(
        ..., ge = 0,
        description = 'How many can be placed on a map, which is what decides '
                      'whether Routes has anything to draw.'
    )


class ClientUpsertResultSchema(BaseModel):
    '''
        Outcome of a load into the master.

        The three counts are separate on purpose: a load that only completed
        empty fields did not change anybody\'s data, and a load that created
        nothing is usually the same file twice.
    '''
    created: int = Field(..., ge = 0)
    completed: int = Field(..., ge = 0, description = 'Existing clients whose empty '
                                                      'fields were filled in.')
    unchanged: int = Field(..., ge = 0)
