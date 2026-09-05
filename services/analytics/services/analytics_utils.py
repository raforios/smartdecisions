'''
    Analytics support: shared DataFrame helpers, the date-range filter, dataset
    loading from the ingest output and persistence of analytics runs.

    Keeps every domain module (analytics.py and the per-question engines) free of
    plumbing: nothing here answers a business question, it only makes the data
    available and the numbers comparable.
'''
import uuid
from decimal import Decimal
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import boto3
import pandas as pd
from boto3.dynamodb.conditions import Attr
from boto3.resources.base import ServiceResource

from schemas.analytics import AnalyticsError, PeriodInfo
from services.crud import create_item
from services.environment import load_and_validate_env_vars
from services.exceptions import (
    InvalidInputError,
    RegisterNotFoundError,
    ServiceUnavailableError
)
from services.logger_config import custom_logger as logger
from services.utils import audit_event, get_current_time_gmt


ENV_VARS = load_and_validate_env_vars({
    'DYNAMODB_TABLE_NAME_INGEST_DATASETS': str,
    'DYNAMODB_TABLE_NAME_ANALYTICS_RUNS': str,
    'BUCKET_NAME': str,
})
INGEST_DATASETS_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_INGEST_DATASETS']
ANALYTICS_RUNS_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_ANALYTICS_RUNS']
FILES_BUCKET_NAME = ENV_VARS['BUCKET_NAME']


# ---------------------------------------------------------------------------
# DataFrame helpers
# ---------------------------------------------------------------------------

AMOUNT = 'total_amount'
QUANTITY = 'quantity'
ORDER = 'order_id'
CLIENT_ID = 'pos_id'
CLIENT_NAME = 'pos_name'
PRODUCT_ID = 'product_id'
PRODUCT_NAME = 'product_name'
PRICE = 'unit_price'
COST = 'unit_cost'
CATEGORY = 'category'
SELLER = 'seller'
DATE = 'date'


def money(value: float) -> float:
    '''
        Rounds a monetary amount to 2 decimals, guarding against NaN.

        Args:
            value (float): Raw amount, possibly NaN coming from pandas.

        Returns:
            float: The amount rounded to 2 decimals, or 0.0 when not a number.
    '''
    return round(float(value), 2) if pd.notna(value) else 0.0


def ratio(numerator: float, denominator: float) -> float:
    '''
        Safe division used across the engines for shares and averages.

        Args:
            numerator (float): Dividend.
            denominator (float): Divisor; a zero or NaN yields 0.0.

        Returns:
            float: The quotient, or 0.0 when the divisor is unusable.
    '''
    if not denominator or pd.isna(denominator):
        return 0.0
    return float(numerator) / float(denominator)


def percent_change(current: float, previous: Optional[float]) -> Optional[float]:
    '''
        Percentage variation between two periods.

        Args:
            current (float): Value of the latest period.
            previous (float | None): Value of the reference period; None or zero
                means there is no base to compare against.

        Returns:
            float | None: The change in percent rounded to 1 decimal, or None
                when there is no comparable base (a growth from zero is
                undefined, not "infinite").
    '''
    if not previous or pd.isna(previous):
        return None
    return round((float(current) - float(previous)) / float(previous) * 100, 1)


def label_series(dataframe: pd.DataFrame, id_col: str, name_col: str) -> Optional[pd.Series]:
    '''
        Returns a readable label per row: the human name when available, else
        the id. Lets rankings show 'Tienda Doña Rosa' instead of 'PDV-007'.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows.
            id_col (str): Column holding the entity id.
            name_col (str): Column holding the human-readable name.

        Returns:
            pd.Series | None: The label per row, or None when neither column
                exists so the caller can skip that section entirely.
    '''
    if name_col in dataframe.columns:
        names = dataframe[name_col].fillna('').astype(str).str.strip()
        ids = dataframe[id_col].astype(str) if id_col in dataframe.columns else ''
        return names.where(names != '', ids)
    if id_col in dataframe.columns:
        return dataframe[id_col].astype(str)
    return None


def dates(dataframe: pd.DataFrame) -> Optional[pd.Series]:
    '''
        Parses the 'date' column into datetimes.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows.

        Returns:
            pd.Series | None: Coerced datetimes (NaT where unparseable), or None
                when the column is absent or holds no usable date at all.
    '''
    if DATE not in dataframe.columns:
        return None
    parsed = pd.to_datetime(dataframe[DATE], errors = 'coerce')
    return parsed if parsed.notna().any() else None


def order_count(dataframe: pd.DataFrame) -> int:
    '''
        Number of distinct orders, falling back to the row count when the file
        has no order id (each line is then its own transaction).

        Args:
            dataframe (pd.DataFrame): Normalized sales rows.

        Returns:
            int: Distinct orders in the frame.
    '''
    if ORDER in dataframe.columns:
        return int(dataframe[ORDER].nunique())
    return int(len(dataframe))


def setting(loaded: dict, name: str, default: Any) -> Any:
    '''
        Reads a tuning knob loaded from the environment, falling back to its
        default when it was not configured.

        Needed because `load_and_validate_env_vars` stores an explicit None for
        every optional variable that is unset, so `dict.get(name, default)`
        returns that None instead of the default. Using `or` would work for the
        current values but would silently discard a legitimate 0.

        Args:
            loaded (dict): Result of `load_and_validate_env_vars`.
            name (str): Variable name.
            default (Any): Value to use when the variable is not configured.

        Returns:
            Any: The configured value, or the default.
    '''
    value = loaded.get(name)
    return default if value is None else value


# ---------------------------------------------------------------------------
# Date range filter
# ---------------------------------------------------------------------------

def _parse_boundary(raw: Optional[str], field: str) -> Optional[pd.Timestamp]:
    '''
        Parses an ISO date coming from the query string.

        Args:
            raw (str | None): Date as 'YYYY-MM-DD'; None means "open end".
            field (str): Field name, used only to build a clear error message.

        Returns:
            pd.Timestamp | None: The parsed boundary, or None when not provided.

        Raises:
            InvalidInputError: If the value is present but not a valid date.
    '''
    if raw is None or str(raw).strip() == '':
        return None
    parsed = pd.to_datetime(raw, errors = 'coerce')
    if pd.isna(parsed):
        error_msg = f'Invalid {field} value "{raw}"; expected format YYYY-MM-DD.'
        logger.warning(error_msg)
        raise InvalidInputError(detail = AnalyticsError.INVALID_DATE.value)
    return parsed


def _describe(available: Tuple[Any, Any],
              applied: Tuple[Any, Any],
              rows: int) -> PeriodInfo:
    '''
        Builds the period descriptor returned alongside every report.

        Args:
            available (tuple): (min, max) dates present in the whole dataset.
            applied (tuple): (from, to) boundaries actually applied, may be None.
            rows (int): Row count after filtering.

        Returns:
            PeriodInfo: Period metadata ready for the UI date pickers.
    '''
    def _iso(value: Any) -> Optional[str]:
        return None if value is None or pd.isna(value) else pd.Timestamp(value).strftime('%Y-%m-%d')

    return PeriodInfo(
        available_from = _iso(available[0]),
        available_to = _iso(available[1]),
        from_date = _iso(applied[0]) or _iso(available[0]),
        to_date = _iso(applied[1]) or _iso(available[1]),
        filtered = applied[0] is not None or applied[1] is not None,
        rows = int(rows)
    )


def apply_date_range(
    dataframe: pd.DataFrame,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    '''
        Restricts a sales frame to a date window and describes the result.

        Rows whose date cannot be parsed are dropped only when a filter is
        actually requested: with no filter the caller keeps the full dataset,
        undated rows included, preserving today's behaviour.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows.
            date_from (str | None): Inclusive lower bound, 'YYYY-MM-DD'.
            date_to (str | None): Inclusive upper bound, 'YYYY-MM-DD'.

        Returns:
            Tuple[pd.DataFrame, Dict[str, Any]]: The scoped frame and the period
                descriptor ('available_from/hasta', 'from_date', 'to_date',
                'filtered', 'rows').

        Raises:
            InvalidInputError: If a boundary is not a valid date, or if the
                requested window leaves no data to analyze.
    '''
    parsed_dates = dates(dataframe)
    lower = _parse_boundary(date_from, 'date_from')
    upper = _parse_boundary(date_to, 'date_to')

    if parsed_dates is None:
        # No usable date column: a filter cannot be honoured, so say so instead
        # of silently returning numbers for the wrong period.
        if lower is not None or upper is not None:
            raise InvalidInputError(detail = AnalyticsError.NO_DATE_COLUMN.value)
        return dataframe, _describe((None, None), (None, None), len(dataframe))

    available = (parsed_dates.min(), parsed_dates.max())
    if lower is None and upper is None:
        return dataframe, _describe(available, (None, None), len(dataframe))

    mask = parsed_dates.notna()
    if lower is not None:
        mask &= parsed_dates >= lower
    if upper is not None:
        # Inclusive upper bound: a plain date means "up to the end of that day".
        mask &= parsed_dates <= upper + pd.Timedelta(days = 1) - pd.Timedelta(seconds = 1)

    scoped = dataframe.loc[mask]
    if scoped.empty:
        error_msg = f'Date range {date_from} → {date_to} matched no rows.'
        logger.warning(error_msg)
        raise InvalidInputError(detail = AnalyticsError.EMPTY_PERIOD.value)

    message = f'Date filter {date_from} → {date_to} kept {len(scoped)} of {len(dataframe)} rows.'
    logger.info(message)
    return scoped, _describe(available, (lower, upper), len(scoped))


# ---------------------------------------------------------------------------
# Dataset loading
# ---------------------------------------------------------------------------


# boto3 resolves region + credentials from the default chain (Lambda IAM
# role in AWS, ~/.aws/credentials in local dev) — same way AUTH and EVENTS
# do it. No region_name argument needed.
_s3_client = boto3.client('s3')


def get_dataset_metadata(
    dynamodb_resource: ServiceResource,
    dataset_id: str
) -> dict:
    '''
        Retrieves a dataset record from the ingest service's table.

        Args:
            dynamodb_resource (ServiceResource): The shared DynamoDB resource.
            dataset_id (str): UUID issued by the ingest service.

        Returns:
            dict: The persisted ingest item.

        Raises:
            RegisterNotFoundError: If the dataset_id is unknown.
            InvalidInputError: If the dataset exists but its status is not 'validated'.
    '''
    # The AWS table `ingest_datasets` uses `id` as its partition key (set
    # to the same UUID value as the logical `dataset_id` attribute by the
    # ingest service — see ingest/services/datasets.py:_build_dataset_item).
    table = dynamodb_resource.Table(INGEST_DATASETS_TABLE)
    response = table.get_item(Key = {'id': dataset_id})
    item = response.get('Item')
    if not item:
        error_msg = f'Dataset {dataset_id} not found in {INGEST_DATASETS_TABLE}.'
        logger.warning(error_msg)
        raise RegisterNotFoundError(detail = error_msg)
    if item.get('status') != 'validated':
        error_msg = (
            f'Dataset {dataset_id} cannot be analyzed because its status is '
            f'"{item.get("status")}". Re-upload a valid file via /v1/ingest/excel.'
        )
        logger.warning(error_msg)
        raise InvalidInputError(detail = error_msg)
    return item


def _read_dataframe(file_bytes: bytes, s3_key: str) -> pd.DataFrame:
    '''
        Parses the downloaded bytes into a DataFrame based on the key suffix.
    '''
    lower = s3_key.lower()
    buffer = BytesIO(file_bytes)
    if lower.endswith('.xlsx'):
        return pd.read_excel(buffer, engine = 'openpyxl')
    if lower.endswith('.csv'):
        return pd.read_csv(buffer)
    error_msg = f'Unsupported file extension on S3 key "{s3_key}".'
    logger.error(error_msg)
    raise InvalidInputError(detail = error_msg)


def load_dataframe_from_s3(s3_key: str) -> pd.DataFrame:
    '''
        Downloads the validated file from S3 and returns it as a DataFrame.

        Args:
            s3_key (str): S3 object key under FILES_BUCKET_NAME.

        Returns:
            pd.DataFrame: Sales rows ready for the affinity engine.

        Raises:
            ServiceUnavailableError: If S3 is unreachable or denies access.
    '''
    try:
        response = _s3_client.get_object(Bucket = FILES_BUCKET_NAME, Key = s3_key)
        file_bytes = response['Body'].read()
    except Exception as error:
        error_msg = (
            f'Failed to download s3://{FILES_BUCKET_NAME}/{s3_key}: {error}'
        )
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(
            detail = AnalyticsError.DATASET_UNREADABLE.value
        ) from error

    message = (
        f'Downloaded {len(file_bytes)} bytes from '
        f's3://{FILES_BUCKET_NAME}/{s3_key} for analytics.'
    )
    logger.info(message)
    return _read_dataframe(file_bytes, s3_key)


# ---------------------------------------------------------------------------
# Run persistence
# ---------------------------------------------------------------------------



def _floats_to_decimal(value: Any) -> Any:
    '''
        Recursively converts floats to Decimal so DynamoDB accepts them.
    '''
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {key: _floats_to_decimal(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [_floats_to_decimal(inner) for inner in value]
    return value


def _decimal_to_native(value: Any) -> Any:
    '''
        Inverse of `_floats_to_decimal` — used when serializing items back to
        the API response (FastAPI / Pydantic don't accept Decimal natively).
    '''
    if isinstance(value, Decimal):
        as_float = float(value)
        return int(as_float) if as_float.is_integer() else as_float
    if isinstance(value, dict):
        return {key: _decimal_to_native(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [_decimal_to_native(inner) for inner in value]
    return value


def _build_run_item(payload: Dict[str, Any]) -> Dict[str, Any]:
    '''
        Materializes the DynamoDB item shape for a finished analytics run.

        The AWS table `analytics_runs` uses a simple partition key `id` (S).
        Each item carries `id = run_id` (UUID) so collisions are impossible,
        and `dataset_id` is a regular attribute used to filter runs by
        dataset.
    '''
    now = get_current_time_gmt()
    run_id = payload.get('run_id') or str(uuid.uuid4())
    return {
        'id': run_id,
        'run_id': run_id,
        'dataset_id': payload['dataset_id'],
        'status': payload['status'],
        'owner_email': payload['owner_email'],
        'summary': _floats_to_decimal(payload.get('summary', {})),
        'opportunities': _floats_to_decimal(payload.get('opportunities', [])),
        'parameters': _floats_to_decimal(payload.get('parameters', {})),
        'created_at': now.isoformat()
    }


@audit_event('ANALYTICS', 'AnalyticsRun', 'CREATE')
def persist_run(
    dynamodb_resource: ServiceResource,
    payload: Dict[str, Any]
) -> Dict[str, Any]:
    '''
        Persists a finished analytics run.
    '''
    item = _build_run_item(payload)
    create_item(
        dynamodb_resource = dynamodb_resource,
        table_name = ANALYTICS_RUNS_TABLE,
        item_data = item,
        unique_key_attribute = 'id'
    )
    message = (
        f'Persisted analytics run {item["run_id"]} for dataset {item["dataset_id"]} '
        f'(status={item["status"]}).'
    )
    logger.info(message)
    return _decimal_to_native(item)


def list_runs_for_owner(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    limit: int = 20
) -> List[Dict[str, Any]]:
    '''
        Returns the caller's own analyses, most recent first.

        The owner is part of the scan filter, the same way the single-run read
        works, so no row of another client can reach the response. With `id` as
        the partition key there is no Query that filters by owner; at POC volumes
        a scan is fine and the right move later is a GSI on `owner_email`.

        Args:
            dynamodb_resource (ServiceResource): DynamoDB resource.
            owner_email (str): Authenticated caller.
            limit (int): Most rows to return.

        Returns:
            List[Dict[str, Any]]: Stored runs, newest first.
    '''
    table = dynamodb_resource.Table(ANALYTICS_RUNS_TABLE)
    items: List[Dict[str, Any]] = []
    scan_kwargs: Dict[str, Any] = {
        'FilterExpression': Attr('owner_email').eq(owner_email)
    }
    while True:
        response = table.scan(**scan_kwargs)
        items.extend(response.get('Items', []))
        last_key = response.get('LastEvaluatedKey')
        if not last_key:
            break
        scan_kwargs['ExclusiveStartKey'] = last_key

    items.sort(key = lambda item: str(item.get('created_at', '')), reverse = True)
    return items[:limit]


def get_latest_run_for_dataset(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    owner_email: str
) -> Dict[str, Any]:
    '''
        Returns the most recent run for the given dataset, if it is the
        caller's.

        The owner is part of the filter, not a check applied afterwards: a run
        belonging to somebody else must be indistinguishable from one that does
        not exist, and comparing after reading invites forgetting the comparison.

        With PK `id`, there is no DynamoDB Query that filters by dataset_id
        directly, so we Scan the table with a FilterExpression. This is OK for
        POC volumes; if the table grows, the right move is a Global Secondary
        Index on `dataset_id`.

        Args:
            dynamodb_resource (ServiceResource): DynamoDB resource.
            dataset_id (str): Dataset the run belongs to.
            owner_email (str): Authenticated caller.

        Returns:
            Dict[str, Any]: The most recent run.

        Raises:
            RegisterNotFoundError: If no run of that dataset belongs to the
                caller.
    '''
    table = dynamodb_resource.Table(ANALYTICS_RUNS_TABLE)
    items: List[Dict[str, Any]] = []
    last_evaluated_key = None
    while True:
        scan_kwargs = {
            'FilterExpression': (Attr('dataset_id').eq(dataset_id)
                                 & Attr('owner_email').eq(owner_email))
        }
        if last_evaluated_key:
            scan_kwargs['ExclusiveStartKey'] = last_evaluated_key
        response = table.scan(**scan_kwargs)
        items.extend(response.get('Items', []))
        last_evaluated_key = response.get('LastEvaluatedKey')
        if not last_evaluated_key:
            break

    if not items:
        error_msg = (f'No analytics run of dataset {dataset_id} is available '
                     f'for {owner_email}.')
        logger.warning(error_msg)
        raise RegisterNotFoundError(detail = AnalyticsError.RUN_NOT_FOUND.value)
    items.sort(key = lambda record: record.get('created_at', ''), reverse = True)
    return _decimal_to_native(items[0])
