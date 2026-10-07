'''
    Pydantic V2 DTOs for the companion contracts pushed as JSON.

    The same three contracts the workbook carries —payments, stock and visits—
    as rows an ERP posts. They exist because of cadence: the sales file is
    loaded once and these change every day, and re-uploading a whole workbook
    to add yesterday's payments is not integration, it is a chore.

    Two rules hold them to the file:

        1. **They ask for exactly what the template asks for.** Nothing more,
           nothing less: the identifiers the service derives on its own are
           not requested here either.
        2. **They are judged by the same validator.** These DTOs carry the
           canonical names, so a pushed row reaches `validate_rows` through the
           same steps a read row does, and answers with the same codes.
'''
import datetime
from enum import Enum
from pydantic import BaseModel, Field


class LoadMode(str, Enum):
    '''
        What a push does to what is already stored.

        APPEND adds the rows and lets the contract's own key decide what is a
        repeat, so an ERP that retries does not count a payment twice and a
        stock push for today replaces today without touching last week.
        REPLACE is what the file does: what arrives becomes the whole load.
    '''
    APPEND = 'APPEND'
    REPLACE = 'REPLACE'


class SaleRowSchema(BaseModel):
    """
        One line of one sale: a product on an invoice.

        It asks for exactly what the template asks for and nothing else — the
        identifiers the service derives are not requested here either. Every
        optional field is optional for the same reason it is in the file:
        without `unit_cost` there is no margin, without coordinates there are
        no routes, and the product says so instead of inventing a zero.
    """
    date: datetime.date
    order_id: str = Field(..., min_length = 1, max_length = 64)
    pos_name: str = Field(..., min_length = 1, max_length = 150)
    product_name: str = Field(..., min_length = 1, max_length = 150)
    quantity: float = Field(..., gt = 0)
    zone: str | None = Field(None, max_length = 100)
    city: str | None = Field(None, max_length = 100)
    region: str | None = Field(None, max_length = 100)
    channel: str | None = Field(None, max_length = 64)
    seller: str | None = Field(None, max_length = 128)
    latitude: float | None = Field(None, ge = -90.0, le = 90.0)
    longitude: float | None = Field(None, ge = -180.0, le = 180.0)
    category: str | None = Field(None, max_length = 100)
    unit_price: float | None = Field(None, ge = 0)
    unit_cost: float | None = Field(None, ge = 0)
    total_amount: float | None = Field(None, ge = 0)
    payment_terms: str | None = Field(None, max_length = 16)
    credit_days: int | None = Field(None, ge = 0)
    due_date: datetime.date | None = None
    collector: str | None = Field(None, max_length = 150)
    credit_limit: float | None = Field(None, ge = 0)


class SalesPushSchema(BaseModel):
    """
        The sales lines an ERP posts into an existing dataset.
    """
    mode: LoadMode = LoadMode.APPEND
    rows: list[SaleRowSchema] = Field(..., min_length = 1)


class CollectionRowSchema(BaseModel):
    '''
        One payment against an invoice of the sales dataset.
    '''
    order_id: str = Field(..., min_length = 1, max_length = 64)
    payment_date: datetime.date
    paid_amount: float = Field(..., gt = 0)
    payment_method: str | None = Field(None, max_length = 32)
    collector: str | None = Field(None, max_length = 150)


class ObjectiveRowSchema(BaseModel):
    """
        One monthly objective an ERP posts for a client.

        `period` is a month and is typed as text, not a date: an objective
        belongs to March, not to any particular day of March, and accepting a
        date here would invite a caller to send the first of the month and a
        second caller the last.
    """
    pos_name: str = Field(..., min_length = 1, max_length = 150)
    period: str = Field(..., pattern = r'^\d{4}-(0[1-9]|1[0-2])$',
                        description = "The month, as 'YYYY-MM'.")
    target_amount: float = Field(..., ge = 0)


class StockRowSchema(BaseModel):
    '''
        What the warehouse holds of one product on one day.

        `committed` is read, never written: this service reports what the ERP
        already committed and holds no reservations of its own.
    '''
    snapshot_date: datetime.date
    product_name: str = Field(..., min_length = 1, max_length = 150)
    on_hand: float = Field(..., ge = 0)
    committed: float | None = Field(None, ge = 0)
    in_transit: float | None = Field(None, ge = 0)
    warehouse: str | None = Field(None, max_length = 64)
    unit_cost: float | None = Field(None, ge = 0)


class VisitRowSchema(BaseModel):
    '''
        One visit the sales force registered on the street.
    '''
    visit_date: datetime.date
    visit_time: str | None = Field(None, max_length = 8)
    seller: str = Field(..., min_length = 1, max_length = 128)
    pos_name: str = Field(..., min_length = 1, max_length = 150)
    latitude: float | None = Field(None, ge = -90.0, le = 90.0)
    longitude: float | None = Field(None, ge = -180.0, le = 180.0)
    outcome: str | None = Field(None, max_length = 16)
    order_id: str | None = Field(None, max_length = 64)


class CollectionsPushSchema(BaseModel):
    '''
        The payments an ERP posts for a sales dataset.
    '''
    mode: LoadMode = LoadMode.APPEND
    rows: list[CollectionRowSchema] = Field(..., min_length = 1)


class ObjectivesPushSchema(BaseModel):
    """
        The monthly objectives an ERP posts for a sales dataset.
    """
    mode: LoadMode = LoadMode.APPEND
    rows: list[ObjectiveRowSchema] = Field(..., min_length = 1)


class StockPushSchema(BaseModel):
    '''
        The stock an ERP posts for a sales dataset.
    '''
    mode: LoadMode = LoadMode.APPEND
    rows: list[StockRowSchema] = Field(..., min_length = 1)


class VisitsPushSchema(BaseModel):
    '''
        The visits an ERP posts for a sales dataset.
    '''
    mode: LoadMode = LoadMode.APPEND
    rows: list[VisitRowSchema] = Field(..., min_length = 1)


class IngestFromS3CompanionRequest(BaseModel):
    '''
        A companion file already staged in S3 by FILES, addressed by its key.

        The binary never crosses API Gateway, which caps a request at about
        10 MB — the same reason the sales file has this door.
    '''
    file_key: str = Field(..., min_length = 1, max_length = 1024)
    file_name: str = Field(..., min_length = 1, max_length = 255)
    mode: LoadMode = LoadMode.REPLACE
