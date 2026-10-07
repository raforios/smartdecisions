'''
    Pydantic V2 DTOs for the Ingest service.

    Holds two things: the sales format contract (SALES_COLUMNS — the single
    definition of the columns, their template headers and their value rules,
    from which the mapper, the DataFrame schema and the required/optional lists
    are derived) and the DTOs that describe the HTTP envelope.
'''
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from pydantic import BaseModel, Field


@dataclass(frozen = True)
class ValueRules:
    '''
        Value constraints of one contract column, grouped so the column itself
        stays readable and within the attribute budget.
    '''
    max_length: int | None = None
    minimum: float | None = None
    exclusive_minimum: float | None = None
    value_range: tuple[float, float] | None = None
    # Accepted values of a closed-option column. It exists because a badly
    # typed payment condition must not pass as cash by omission: that would
    # change the receivable balance without anybody noticing.
    allowed: tuple[str, ...] | None = None


@dataclass(frozen = True)
class SalesColumn:
    '''
        One column of the sales contract.

        This is the single source of truth for the ingest format: the canonical
        name the engine uses, the header the published template carries, whether
        the analysis can run without it, and the value rules it must satisfy.
        The header mapper, the required/optional lists and the DataFrame schema
        are all derived from here, so the contract is stated once.
    '''
    canonical: str
    header: str
    # Required in the VALIDATED frame — what the engine cannot work without.
    required: bool
    dtype: str
    rules: ValueRules = ValueRules()
    # Required in the FILE THE CLIENT FILLS IN. Not the same thing: the client
    # writes 'Cliente' and the service derives 'pos_id' from it, so the name is
    # mandatory for them while the identifier is mandatory for the engine.
    template_required: bool = False
    # Identifiers the service derives on its own; the template never asks for
    # them because the client has no such codes.
    filled_by_service: bool = False


# Order is the contract order: the template presents its columns like this.
SALES_COLUMNS: tuple[SalesColumn, ...] = (
    SalesColumn('date', 'Fecha', True, 'datetime64[ns]', template_required = True),
    SalesColumn('order_id', 'Nro Factura', True, 'object',
                rules = ValueRules(max_length = 64), template_required = True),
    SalesColumn('pos_id', 'Cliente ID', True, 'object',
                rules = ValueRules(max_length = 64), filled_by_service = True),
    SalesColumn('pos_name', 'Cliente', False, 'object', template_required = True),
    SalesColumn('zone', 'Zona', False, 'object'),
    SalesColumn('city', 'Ciudad', False, 'object'),
    SalesColumn('region', 'Region', False, 'object'),
    SalesColumn('channel', 'Canal', False, 'object'),
    SalesColumn('seller', 'Vendedor', False, 'object'),
    SalesColumn('latitude', 'Latitud', False, 'float64',
                rules = ValueRules(value_range = (-90.0, 90.0))),
    SalesColumn('longitude', 'Longitud', False, 'float64',
                rules = ValueRules(value_range = (-180.0, 180.0))),
    SalesColumn('product_id', 'Producto ID', True, 'object',
                rules = ValueRules(max_length = 64), filled_by_service = True),
    SalesColumn('product_name', 'Producto', False, 'object', template_required = True),
    SalesColumn('category', 'Categoria', False, 'object'),
    SalesColumn('quantity', 'Cantidad', True, 'float64',
                rules = ValueRules(exclusive_minimum = 0.0), template_required = True),
    SalesColumn('unit_price', 'Precio Unitario', False, 'float64',
                rules = ValueRules(minimum = 0.0)),
    SalesColumn('unit_cost', 'Costo Unitario', False, 'float64',
                rules = ValueRules(minimum = 0.0)),
    SalesColumn('total_amount', 'Monto Total', False, 'float64',
                rules = ValueRules(minimum = 0.0)),
    # --- Credit: what is known at the moment of the sale --------------------
    # Optional. Without them the receivables analysis is not offered; with them
    # it turns on without the client loading anything separately.
    SalesColumn('payment_terms', 'Condicion Venta', False, 'object',
                rules = ValueRules(max_length = 16,
                                   allowed = ('CONTADO', 'CREDITO'))),
    SalesColumn('credit_days', 'Plazo Dias', False, 'Int64',
                rules = ValueRules(minimum = 0.0)),
    SalesColumn('due_date', 'Fecha Vencimiento', False, 'datetime64[ns]'),
    SalesColumn('collector', 'Responsable Cobro', False, 'object'),
    SalesColumn('credit_limit', 'Limite Credito', False, 'float64',
                rules = ValueRules(minimum = 0.0)),
)

# The payment is a separate contract, married to the sale by `order_id` and
# loaded afterwards: an invoice at 90 days is collected three months after the
# file that registered it. It shares the `SalesColumn` type because it is the
# same kind of declaration; what changes is the sheet it lives on.
COLLECTION_COLUMNS: tuple[SalesColumn, ...] = (
    SalesColumn('order_id', 'Nro Factura', True, 'object',
                rules = ValueRules(max_length = 64), template_required = True),
    SalesColumn('payment_date', 'Fecha Cobro', True, 'datetime64[ns]',
                template_required = True),
    SalesColumn('paid_amount', 'Monto Cobrado', True, 'float64',
                rules = ValueRules(exclusive_minimum = 0.0),
                template_required = True),
    SalesColumn('payment_method', 'Medio', False, 'object',
                rules = ValueRules(max_length = 32)),
    SalesColumn('collector', 'Responsable Cobro', False, 'object'),
)

COLLECTION_HEADERS: tuple[str, ...] = tuple(
    column.header for column in COLLECTION_COLUMNS
)


# The objective is what the company DECIDED a client should buy in a month,
# and it is the only figure in the product that does not come from a
# transaction: nothing in a sales file implies it. It arrives per client and
# per month because that is the grain the commercial team manages — the same
# objective is then measured twice, against what was invoiced and against what
# was actually collected, which is the difference between selling and getting
# paid.
OBJECTIVE_COLUMNS: tuple[SalesColumn, ...] = (
    SalesColumn('pos_id', 'Cliente ID', True, 'object',
                rules = ValueRules(max_length = 64), filled_by_service = True),
    SalesColumn('pos_name', 'Cliente', True, 'object', template_required = True),
    SalesColumn('period', 'Periodo', True, 'object',
                rules = ValueRules(max_length = 7), template_required = True),
    SalesColumn('target_amount', 'Objetivo', True, 'float64',
                rules = ValueRules(minimum = 0.0), template_required = True),
)

OBJECTIVE_HEADERS: tuple[str, ...] = tuple(
    column.header for column in OBJECTIVE_COLUMNS if not column.filled_by_service
)

# The stock is a SNAPSHOT, not a movement ledger: one row per product and day
# with what was in the warehouse. It has its own endpoint because it changes
# every day while the sales file is loaded once, and because the ERP that
# exports it is rarely the same system that issues the invoices.
#
# `Comprometido` is what the ERP already committed in orders: it is READ, never
# written. SmartDecisions holds no reservations — it would own the truth of the
# stock and lose that fight against the ERP.
STOCK_COLUMNS: tuple[SalesColumn, ...] = (
    SalesColumn('snapshot_date', 'Fecha', True, 'datetime64[ns]',
                template_required = True),
    SalesColumn('product_id', 'Producto ID', True, 'object',
                rules = ValueRules(max_length = 64), filled_by_service = True),
    SalesColumn('product_name', 'Producto', False, 'object', template_required = True),
    SalesColumn('on_hand', 'Existencia', True, 'float64',
                rules = ValueRules(minimum = 0.0), template_required = True),
    SalesColumn('committed', 'Comprometido', False, 'float64',
                rules = ValueRules(minimum = 0.0)),
    SalesColumn('in_transit', 'En Transito', False, 'float64',
                rules = ValueRules(minimum = 0.0)),
    SalesColumn('warehouse', 'Almacen', False, 'object',
                rules = ValueRules(max_length = 64)),
    SalesColumn('unit_cost', 'Costo Unitario', False, 'float64',
                rules = ValueRules(minimum = 0.0)),
)

STOCK_HEADERS: tuple[str, ...] = tuple(
    column.header for column in STOCK_COLUMNS if not column.filled_by_service
)

# A visit is what the seller's system registered on the street: who was
# visited, when, and —if that system knows it— what came of it. It is the
# EXECUTED side of the route; the planned side comes from OPTIMIZATION. The
# sheet is optional like the other companions: without it the route module
# plans and nothing else. Coordinates and the outcome are optional because
# most systems export the visit and not the GPS reading; with the outcome the
# comparison goes from "was there" to "was there and sold".
VISIT_COLUMNS: tuple[SalesColumn, ...] = (
    SalesColumn('visit_date', 'Fecha', True, 'datetime64[ns]',
                template_required = True),
    SalesColumn('visit_time', 'Hora', False, 'object',
                rules = ValueRules(max_length = 8)),
    SalesColumn('seller', 'Vendedor', True, 'object',
                rules = ValueRules(max_length = 128), template_required = True),
    SalesColumn('pos_id', 'Cliente ID', True, 'object',
                rules = ValueRules(max_length = 64), filled_by_service = True),
    SalesColumn('pos_name', 'Cliente', False, 'object', template_required = True),
    SalesColumn('latitude', 'Latitud', False, 'float64',
                rules = ValueRules(value_range = (-90.0, 90.0))),
    SalesColumn('longitude', 'Longitud', False, 'float64',
                rules = ValueRules(value_range = (-180.0, 180.0))),
    SalesColumn('outcome', 'Resultado', False, 'object',
                rules = ValueRules(max_length = 16,
                                   allowed = ('VENTA', 'SIN_VENTA', 'CERRADO',
                                              'NO_ENCONTRADO'))),
    SalesColumn('order_id', 'Nro Factura', False, 'object',
                rules = ValueRules(max_length = 64)),
)

VISIT_HEADERS: tuple[str, ...] = tuple(
    column.header for column in VISIT_COLUMNS if not column.filled_by_service
)

# The client master. What describes WHO buys is stated once here and not
# repeated on every sales line: the transaction file only identifies the
# client, and whatever it omits is taken from this master. That is what lets a
# company upload sales without coordinates on Tuesday and still have Routes
# working, and what lets a seller register a client from the street.
#
# `id` is the code the client's own system uses; it is the identity of the
# record, so it is required everywhere and is never derived by the service.
CLIENT_COLUMNS: tuple[SalesColumn, ...] = (
    SalesColumn('id', 'Cliente ID', True, 'object',
                rules = ValueRules(max_length = 64), template_required = True),
    SalesColumn('name', 'Cliente', True, 'object',
                rules = ValueRules(max_length = 150), template_required = True),
    SalesColumn('tax_id', 'NIT', False, 'object',
                rules = ValueRules(max_length = 40)),
    SalesColumn('client_type', 'Tipo Negocio', False, 'object',
                rules = ValueRules(max_length = 64)),
    SalesColumn('channel', 'Canal', False, 'object',
                rules = ValueRules(max_length = 64)),
    SalesColumn('zone', 'Zona', False, 'object', rules = ValueRules(max_length = 100)),
    SalesColumn('city', 'Ciudad', False, 'object', rules = ValueRules(max_length = 100)),
    SalesColumn('region', 'Region', False, 'object', rules = ValueRules(max_length = 100)),
    SalesColumn('address', 'Direccion', False, 'object',
                rules = ValueRules(max_length = 255)),
    SalesColumn('latitude', 'Latitud', False, 'float64',
                rules = ValueRules(value_range = (-90.0, 90.0))),
    SalesColumn('longitude', 'Longitud', False, 'float64',
                rules = ValueRules(value_range = (-180.0, 180.0))),
    SalesColumn('phone', 'Telefono', False, 'object',
                rules = ValueRules(max_length = 40)),
    SalesColumn('contact', 'Contacto', False, 'object',
                rules = ValueRules(max_length = 150)),
    SalesColumn('seller', 'Vendedor', False, 'object',
                rules = ValueRules(max_length = 128)),
    SalesColumn('credit_limit', 'Limite Credito', False, 'float64',
                rules = ValueRules(minimum = 0.0)),
    # The commercial hierarchy a client is managed through. It is GIVEN, never
    # deduced: the cluster is a decision the company makes about a client, not
    # a tier computed from their sales — which is what `segmentation` already
    # does, and a different question.
    SalesColumn('cluster', 'Cluster', False, 'object',
                rules = ValueRules(max_length = 40)),
    SalesColumn('supervisor', 'Supervisor', False, 'object',
                rules = ValueRules(max_length = 128)),
    SalesColumn('market', 'Mercado', False, 'object',
                rules = ValueRules(max_length = 100)),
)

CLIENT_HEADERS: tuple[str, ...] = tuple(
    column.header for column in CLIENT_COLUMNS if not column.filled_by_service
)

# The attributes the sales, stock and visit files may carry about the client
# and that therefore feed the master when they arrive. Stated once so the
# enrichment and the upsert cannot drift apart.
CLIENT_SALES_ATTRIBUTES: tuple[str, ...] = (
    'name', 'zone', 'city', 'region', 'channel',
    'latitude', 'longitude', 'seller', 'credit_limit',
    'cluster', 'supervisor', 'market',
)

# One file per contract, so the contract IS the file and these are the names
# of the templates the client downloads — not sheets inside one workbook. The
# four-sheet book was our own invention: it made the service read S3 by itself,
# because a reader that returns one flat table could not serve it.
SALES_TEMPLATE: str = 'ventas'
COLLECTIONS_TEMPLATE: str = 'cobros'
STOCK_TEMPLATE: str = 'stock'
VISITS_TEMPLATE: str = 'visitas'
CLIENTS_TEMPLATE: str = 'clientes'
OBJECTIVES_TEMPLATE: str = 'objetivos'


class TemplateName(str, Enum):
    '''
        The templates a client can download, one per contract.
    '''
    SALES = SALES_TEMPLATE
    COLLECTIONS = COLLECTIONS_TEMPLATE
    STOCK = STOCK_TEMPLATE
    VISITS = VISITS_TEMPLATE
    OBJECTIVES = OBJECTIVES_TEMPLATE

TEMPLATE_VERSION: str = 'v4'

REQUIRED_COLUMNS: tuple[str, ...] = tuple(
    column.canonical for column in SALES_COLUMNS if column.required
)
OPTIONAL_COLUMNS: tuple[str, ...] = tuple(
    column.canonical for column in SALES_COLUMNS if not column.required
)
# What the published template asks for: everything except the identifiers the
# service derives on its own.
TEMPLATE_COLUMNS: tuple[SalesColumn, ...] = tuple(
    column for column in SALES_COLUMNS if not column.filled_by_service
)
TEMPLATE_HEADERS: tuple[str, ...] = tuple(column.header for column in TEMPLATE_COLUMNS)


class ValidationRule(str, Enum):
    '''
        Why a row failed validation.

        A stable code, never a sentence: the wording belongs to whoever shows it
        (today the frontend catalogue, tomorrow the interpretation layer), and
        pinning prose here would leave both of them parsing text instead of
        reading facts.
    '''
    REQUIRED_VALUE = 'REQUIRED_VALUE'
    INVALID_TYPE = 'INVALID_TYPE'
    TEXT_LENGTH = 'TEXT_LENGTH'
    BELOW_MINIMUM = 'BELOW_MINIMUM'
    OUT_OF_RANGE = 'OUT_OF_RANGE'
    UNKNOWN_COLUMN = 'UNKNOWN_COLUMN'
    MISSING_COLUMN = 'MISSING_COLUMN'
    EMPTY_FILE = 'EMPTY_FILE'
    INVALID_VALUE = 'INVALID_VALUE'
    # Collections: the invoice is not in the sales dataset, or more was
    # collected than was billed. Both are reported and never dropped: they are
    # facts of the client's file, and deciding what they mean is not this
    # service's call.
    UNKNOWN_INVOICE = 'UNKNOWN_INVOICE'
    OVERPAID_INVOICE = 'OVERPAID_INVOICE'
    # Stock: the product in the snapshot is not in the sales catalogue.
    UNKNOWN_PRODUCT = 'UNKNOWN_PRODUCT'
    # Visits: the client or the seller is not in the sales dataset. Reported,
    # never dropped: a visit to a prospect is a fact worth keeping.
    UNKNOWN_CLIENT = 'UNKNOWN_CLIENT'
    UNKNOWN_SELLER = 'UNKNOWN_SELLER'


class IngestError(str, Enum):
    '''
        Why a request could not be processed at all.

        Travels as the error `detail`, so the client reads a stable code and
        renders its own wording. Same reasoning as ValidationRule: prose in the
        backend cannot be translated and cannot be interpreted.
    '''
    UNSUPPORTED_FILE_FORMAT = 'UNSUPPORTED_FILE_FORMAT'
    EMPTY_UPLOAD = 'EMPTY_UPLOAD'
    FILES_SERVICE_UNREACHABLE = 'FILES_SERVICE_UNREACHABLE'
    FILES_SERVICE_REJECTED_UPLOAD = 'FILES_SERVICE_REJECTED_UPLOAD'
    DATASET_NOT_FOUND = 'DATASET_NOT_FOUND'
    NO_REJECTED_ROWS = 'NO_REJECTED_ROWS'
    NO_STOCK_FOR_DAY = 'NO_STOCK_FOR_DAY'


class ValidationIssue(BaseModel):
    '''
        One cell (or one column) that failed the template contract.
    '''
    row: int = Field(..., description = 'Excel row number (1-based, header is row 1).')
    column: str = Field(..., description = 'Column name where the issue occurred.')
    value: str | None = Field(None, description = 'Raw value that failed validation.')
    rule_code: ValidationRule = Field(..., description = 'Why it failed.')


class IngestSummary(BaseModel):
    '''
        High-level outcome of an ingest attempt.
    '''
    total_rows: int = Field(..., ge = 0)
    valid_rows: int = Field(..., ge = 0)
    error_rows: int = Field(..., ge = 0)
    unique_points_of_sale: int = Field(..., ge = 0)
    unique_products: int = Field(..., ge = 0)
    date_range_start: str | None = Field(None,
                    description = 'ISO date of the earliest valid sale.')
    date_range_end: str | None = Field(None,
                    description = 'ISO date of the latest valid sale.')


class ObjectivesSummary(BaseModel):
    """
        What an objectives load contains, once matched to its sales dataset.

        `unmatched_rows` travels for the same reason it does in a collections
        load, but it means the opposite thing: a client with an objective and
        no invoice is not a mistake, it is a client the company expects to
        activate — and that is precisely the row a manager wants on the
        screen.
    """
    total_rows: int = Field(0, ge = 0)
    valid_rows: int = Field(0, ge = 0)
    error_rows: int = Field(0, ge = 0)
    clients_with_objective: int = Field(0, ge = 0)
    unmatched_rows: int = Field(0, ge = 0)
    periods_count: int = Field(0, ge = 0)
    target_amount: float = Field(0.0, ge = 0)
    period_start: str | None = Field(None, description = "'YYYY-MM', if any.")
    period_end: str | None = Field(None, description = "'YYYY-MM', if any.")


class CollectionsSummary(BaseModel):
    '''
        What a collections load contains, once married to its sales dataset.

        `unmatched_rows` travels because it is the number that says whether the
        two files belong together: a load where nothing matched is almost
        always the wrong dataset, not a client who paid nothing.
    '''
    total_rows: int = Field(0, ge = 0)
    valid_rows: int = Field(0, ge = 0)
    error_rows: int = Field(0, ge = 0)
    matched_invoices: int = Field(0, ge = 0)
    unmatched_rows: int = Field(0, ge = 0)
    collected_amount: float = Field(0.0, ge = 0)
    payment_date_start: str | None = Field(None, description = 'ISO date, if any.')
    payment_date_end: str | None = Field(None, description = 'ISO date, if any.')


class StockSummary(BaseModel):
    '''
        What a stock snapshot load contains.

        `unknown_products` travels because it is the number that says whether
        the snapshot belongs to this dataset: a load where nothing matched the
        catalogue is the wrong file, not a warehouse full of new products.
    '''
    total_rows: int = Field(0, ge = 0)
    valid_rows: int = Field(0, ge = 0)
    error_rows: int = Field(0, ge = 0)
    products: int = Field(0, ge = 0)
    unknown_products: int = Field(0, ge = 0)
    units_on_hand: float = Field(0.0)
    snapshot_start: str | None = Field(None, description = 'ISO date, if any.')
    snapshot_end: str | None = Field(None, description = 'ISO date, if any.')


class VisitsSummary(BaseModel):
    '''
        What a visits load contains.

        `unknown_clients` and `unknown_sellers` travel because they say whether
        the file belongs to this dataset: a load where nobody matches is the
        wrong file, not a new sales force.
    '''
    total_rows: int = Field(0, ge = 0)
    valid_rows: int = Field(0, ge = 0)
    error_rows: int = Field(0, ge = 0)
    sellers: int = Field(0, ge = 0)
    clients: int = Field(0, ge = 0)
    unknown_clients: int = Field(0, ge = 0)
    unknown_sellers: int = Field(0, ge = 0)
    with_coordinates: int = Field(0, ge = 0, description = 'Rows carrying a GPS pair.')
    with_outcome: int = Field(0, ge = 0, description = 'Rows carrying a result code.')
    visit_date_start: str | None = Field(None, description = 'ISO date, if any.')
    visit_date_end: str | None = Field(None, description = 'ISO date, if any.')


class VisitsResponse(BaseModel):
    '''
        Answer of a visits upload: what got in, what did not, and why.
    '''
    dataset_id: str = Field(..., description = 'Sales dataset the visits belong to.')
    status: str = Field(..., description = "'validated' or 'failed'.")
    visits_s3_key: str | None = Field(
        None, description = 'Object key of the stored visits file.'
    )
    summary: VisitsSummary = VisitsSummary()
    issues: list[ValidationIssue] = Field(default_factory = list)


class StockResponse(BaseModel):
    '''
        Answer of a stock upload: what got in, what did not, and why.
    '''
    dataset_id: str = Field(..., description = 'Sales dataset the snapshot belongs to.')
    status: str = Field(..., description = "'validated' or 'failed'.")
    stock_s3_key: str | None = Field(
        None, description = 'Object key of the stored snapshot file.'
    )
    summary: StockSummary = StockSummary()
    issues: list[ValidationIssue] = Field(default_factory = list)


class StockDayItem(BaseModel):
    '''
        One product of the snapshot of a single day.

        `available` is `on_hand - committed`: the units the ERP has not already
        promised, which are the ones a seller can still sell on the street.
    '''
    product_id: str
    product_name: str | None = None
    on_hand: float = Field(..., ge = 0)
    committed: float = Field(0.0, ge = 0)
    available: float = Field(..., ge = 0)


class StockDayResponse(BaseModel):
    '''
        The stored snapshot of one day, for GET /v1/ingest/{dataset_id}/stock.

        It exists so a service that needs the stock asks INGEST for it instead
        of reading the file: the route module opens its day with the same file
        the analysis reads.
    '''
    dataset_id: str
    date: str = Field(..., description = 'YYYY-MM-DD.')
    items: list[StockDayItem] = Field(default_factory = list)


class ObjectivesResponse(BaseModel):
    """
        Answer of an objectives upload: what got in, what did not, and why.

        Parallel to the other companions —`<name>_s3_key`, summary, issues—
        because one storage routine serves them all.
    """
    dataset_id: str = Field(..., description = 'Sales dataset the objectives belong to.')
    status: str = Field(..., description = "'validated' or 'failed'.")
    objectives_s3_key: str | None = Field(
        None, description = 'Object key of the stored objectives file.'
    )
    summary: ObjectivesSummary = ObjectivesSummary()
    issues: list[ValidationIssue] = Field(default_factory = list)


class CollectionsResponse(BaseModel):
    '''
        Answer of a collections upload: what got in, what did not, and why.
    '''
    dataset_id: str = Field(..., description = 'Sales dataset the payments belong to.')
    status: str = Field(..., description = "'validated' or 'failed'.")
    collections_s3_key: str | None = Field(
        None, description = 'Object key of the stored payments file.'
    )
    summary: CollectionsSummary = CollectionsSummary()
    issues: list[ValidationIssue] = Field(default_factory = list)


class IngestResponse(BaseModel):
    '''
        Response payload returned after a successful ingest.

        `status = 'validated'` means the file passed the structural contract and
        is ready for downstream analysis (paso 3 of the POC). `status = 'failed'`
        means the file was uploaded but rejected: `errors` lists per-row issues.
    '''
    dataset_id: str
    already_stored: bool = Field(
        False,
        description = 'True when the file was already loaded: same owner, same '
                      'content. Nothing was written and the existing dataset is '
                      'returned.'
    )
    status: str = Field(..., description = "'validated' or 'failed'.")
    file_s3_key: str = Field(..., description = 'Object key in the S3 bucket managed by FILES.')
    summary: IngestSummary
    issues: list[ValidationIssue] = Field(default_factory = list)
    collections: CollectionsSummary | None = Field(
        None,
        description = 'Filled when the uploaded workbook also carried a payments '
                      'sheet, so one upload answers both contracts.'
    )
    stock: StockSummary | None = Field(
        None,
        description = 'Filled when the uploaded workbook also carried a stock '
                      'sheet: the same upload feeds the stock module too.'
    )
    visits: VisitsSummary | None = Field(
        None,
        description = 'Filled when the uploaded workbook also carried a visits '
                      'sheet: the executed side of the routes.'
    )
    created_at: datetime


class DatasetSummary(BaseModel):
    '''
        One row of "my uploads".

        Deliberately lighter than IngestStatusResponse: a history list needs to
        say what was uploaded and how it went, not carry every validation issue
        of every file.
    '''
    dataset_id: str
    status: str
    total_rows: int = 0
    valid_rows: int = 0
    error_rows: int = 0
    unique_points_of_sale: int = 0
    unique_products: int = 0
    date_range_start: date | None = None
    date_range_end: date | None = None
    created_at: datetime


class DatasetListResponse(BaseModel):
    '''
        The caller's own uploads, most recent first.

        Only the caller's: the owner is part of the query, not a filter applied
        afterwards. Ordering matters as much as the content — the screen that
        consumes this shows "your last upload", which is the first row.
    '''
    owner_email: str
    count: int = Field(..., ge = 0)
    datasets: list[DatasetSummary] = Field(default_factory = list)


class IngestStatusResponse(BaseModel):
    '''
        Compact metadata for `GET /ingest/{dataset_id}`. `status` is
        'validated' or 'failed'.
    '''
    dataset_id: str
    status: str
    owner_email: str
    file_s3_key: str
    summary: IngestSummary
    issues: list[ValidationIssue] = Field(default_factory = list)
    collections: CollectionsSummary | None = Field(
        None,
        description = 'Payments loaded against this dataset, when there are any. '
                      'Its absence is what tells the frontend not to offer the '
                      'receivables view.'
    )
    stock: StockSummary | None = Field(
        None,
        description = 'Latest stock snapshot loaded against this dataset, when '
                      'there is one. A new load replaces the previous snapshot.'
    )
    visits: VisitsSummary | None = Field(
        None,
        description = 'Visits loaded against this dataset, when there are any: '
                      'the executed side of the routes.'
    )
    created_at: datetime


class IngestFromS3Request(BaseModel):
    '''
        Request for ingesting a file already uploaded to S3 via a pre-signed URL.

        Large files (real sales exports easily exceed the 10 MB API Gateway limit)
        are uploaded directly to S3 by the browser; the service then reads them
        from S3 by key, so no big binary ever transits API Gateway / Lambda.
    '''
    file_key: str = Field(..., min_length = 1,
                description = 'S3 object key of the raw uploaded file.')
    file_name: str = Field(..., min_length = 1,
                description = 'Original filename (drives format detection: .xlsx/.csv).')


class TemplateInfo(BaseModel):
    '''
        Metadata describing the canonical Excel template version.
    '''
    template_version: str = Field(...,
                description = "Semantic version of the contract, e.g. 'v1'.")
    download_url: str = Field(...,
                description = 'Pre-signed URL or static URL to download the template.')
    required_columns: list[str]
    optional_columns: list[str]
