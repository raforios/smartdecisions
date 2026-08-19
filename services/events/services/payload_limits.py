'''
    Payload size limits for stored log bodies.

    A usage log keeps the request and the response of every call. Storing them
    whole is what took the BINARIA `usage_logs` table to 10.6 GB across 827k
    records (13.5 KB average per item), and item size is what makes every read
    slow and every index expensive.

    Bodies are therefore capped before being written. The cap is deliberately
    generous — enough to diagnose a call — and leaves a visible marker so nobody
    mistakes a truncated body for the real payload.
'''
import json
from typing import Any, Dict, List

from services.environment import load_and_validate_env_vars
from services.logger_config import custom_logger as logger

DEFAULT_MAX_BODY_CHARS = 2000
TRUNCATION_MARKER = '…[truncado por EVENTS]'
BODY_FIELDS = ('request_body', 'response_body')
# Audit records carry the entity state instead of HTTP bodies; they grow the
# same way and are capped with the same rule.
AUDIT_BODY_FIELDS = ('old_values', 'new_values')
ALL_BODY_FIELDS = BODY_FIELDS + AUDIT_BODY_FIELDS

# Overridable per environment; the default keeps a log entry near 1 KB.
ENV_VARS = load_and_validate_env_vars({}, {'MAX_BODY_CHARS': int})


def _max_chars() -> int:
    '''
        Returns the configured cap, falling back to the default.
    '''
    return ENV_VARS.get('MAX_BODY_CHARS') or DEFAULT_MAX_BODY_CHARS


def truncate_body(value: Any, max_chars: int = None) -> Any:
    '''
        Caps a single body field.

        Serializes structured bodies to text before measuring, because what
        costs storage is the serialized size, not the number of keys. A body
        already under the cap is returned untouched, so small payloads keep
        their original structure.

        Args:
            value (Any): Body as received (dict, list, str or None).
            max_chars (int): Override for the cap.

        Returns:
            Any: The original value, or a truncated string with the marker.
    '''
    if value is None:
        return None

    limit = max_chars or _max_chars()
    if isinstance(value, str):
        rendered = value
    else:
        try:
            rendered = json.dumps(value, ensure_ascii = False, default = str)
        except (TypeError, ValueError):
            rendered = str(value)

    if len(rendered) <= limit:
        return value
    return rendered[:limit] + TRUNCATION_MARKER


def cap_log_bodies(record: Dict[str, Any], max_chars: int = None) -> Dict[str, Any]:
    '''
        Caps every body field of a log record.

        Applied on write so new records stay small, and on read so a page of
        historical records — written before the cap existed — cannot blow past
        the 6 MB response limit of Lambda.

        Args:
            record (Dict[str, Any]): Record to cap, in place.
            max_chars (int): Override for the cap.

        Returns:
            Dict[str, Any]: The same record, with oversized bodies truncated.
    '''
    for field in ALL_BODY_FIELDS:
        if field not in record:
            continue
        original = record[field]
        capped = truncate_body(original, max_chars)
        if capped is not original:
            record[field] = capped
            message = f'Body "{field}" truncated.'
            logger.debug(message)
    return record


def cap_many(records: List[Dict[str, Any]], max_chars: int = None) -> List[Dict[str, Any]]:
    '''
        Caps the bodies of a whole page of records before returning them.

        A listing of 100 historical records, each carrying a full response
        body, exceeded the 6 MB Lambda response limit and turned into a 500.

        Args:
            records (List[Dict[str, Any]]): Page about to be returned.
            max_chars (int): Override for the cap.

        Returns:
            List[Dict[str, Any]]: The same records, capped.
    '''
    return [cap_log_bodies(record, max_chars) for record in records]
