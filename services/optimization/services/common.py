'''
    Helpers shared by the planning (`optimization.*`) and the tracking
    (`localization.*`) processes of this service. Anything both need lives here
    once; neither imports the other.
'''
import math
from decimal import Decimal
from uuid import uuid4

from schemas.optimization import OptimizationError
from services.exceptions import InvalidInputError
from services.logger_config import custom_logger as logger
from services.utils import get_current_time_gmt

# Mean Earth radius — a physical constant, not a business choice.
EARTH_RADIUS_M = 6_371_000.0


def calculate_distance(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float
) -> float:
    '''
        Great-circle distance between two coordinates, in metres (haversine).

        Args:
            lat1 (float): Latitude of the first point.
            lon1 (float): Longitude of the first point.
            lat2 (float): Latitude of the second point.
            lon2 (float): Longitude of the second point.

        Returns:
            float: Distance in metres.
    '''
    lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
    lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)
    delta_lat = lat2_rad - lat1_rad
    delta_lon = lon2_rad - lon1_rad
    a = (math.sin(delta_lat / 2) ** 2
         + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
    return EARTH_RADIUS_M * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def new_id() -> str:
    '''
        Identifier for a new item.

        Returns:
            str: A random UUID.
    '''
    return str(uuid4())


def now_iso() -> str:
    '''
        Current time in the service timezone, ISO 8601 to the second.

        Returns:
            str: Timestamp such as "2026-09-20T08:30:00-04:00".
    '''
    return get_current_time_gmt().isoformat(timespec = 'seconds')


def from_dynamo(value):
    '''
        Turns the Decimals DynamoDB hands back into native numbers, recursively,
        so DTOs and arithmetic never meet a Decimal.

        Args:
            value: An item, a list of items or a scalar as returned by boto3.

        Returns:
            The same structure with int/float instead of Decimal.
    '''
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, list):
        return [from_dynamo(element) for element in value]
    if isinstance(value, dict):
        return {key: from_dynamo(element) for key, element in value.items()}
    return value


def to_dynamo(value):
    '''
        The inverse of `from_dynamo`: floats become Decimal so boto3 accepts the
        item. Ints and everything else pass through.

        Args:
            value: An item, a list or a scalar about to be written.

        Returns:
            The same structure with Decimal instead of float.
    '''
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, list):
        return [to_dynamo(element) for element in value]
    if isinstance(value, dict):
        return {key: to_dynamo(element) for key, element in value.items()}
    return value


CSV_EXTENSIONS = ('.csv', '.txt')


def decode_csv_upload(
    filename: str,
    raw_bytes: bytes
) -> str:
    '''
        Turns an uploaded CSV into text, refusing what cannot be a CSV. Shared
        by every bulk-upload endpoint of the service so they all answer the
        same codes.

        Args:
            filename (str): Name the client gave the file.
            raw_bytes (bytes): Its content.

        Returns:
            str: The file decoded as UTF-8 (BOM tolerated).

        Raises:
            InvalidInputError: UNSUPPORTED_FILE_TYPE, EMPTY_UPLOAD or
                INVALID_ENCODING.
    '''
    if not (filename or '').lower().endswith(CSV_EXTENSIONS):
        error_msg = f'Upload refused: {filename!r} is not a CSV.'
        logger.warning(error_msg)
        raise InvalidInputError(detail = OptimizationError.UNSUPPORTED_FILE_TYPE.value)
    if not raw_bytes:
        raise InvalidInputError(detail = OptimizationError.EMPTY_UPLOAD.value)
    try:
        return raw_bytes.decode('utf-8-sig')
    except UnicodeDecodeError as error:
        error_msg = f'Upload refused: {filename!r} is not UTF-8.'
        logger.warning(error_msg)
        raise InvalidInputError(detail = OptimizationError.INVALID_ENCODING.value) from error
