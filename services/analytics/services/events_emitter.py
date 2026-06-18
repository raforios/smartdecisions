'''
    Events emitter — adapted port of the TRADE microservice's audit/usage_log
    pattern (`services/trade/services/utils.py`) to DynamoDB-backed services.

    Why this lives in a separate module:
        The `services/utils.py` of all DynamoDB services is contract-shared
        boilerplate (see feedback memory `feedback-boilerplate-standard`). To
        avoid diverging that contract, the EVENTS-emitter additions go here.

    Why this is not a verbatim copy of TRADE's utils.py:
        TRADE depends on SQLAlchemy + Session. This service is Dynamo-only, so
        the SQL-specific helpers (`_handle_exception` with rollback,
        `sqlalchemy_object_as_dict`) are dropped. The audit / usage_log shape
        sent to EVENTS is identical.

    Two pieces are exposed:
        - `audit_event(microservice, entity_name, action)` — decorator factory
          for service-layer functions that mutate state. Sends a fire-and-forget
          audit event after the wrapped function returns.
        - `log_usage(microservice)` — decorator factory for route-layer
          functions. Captures request/response/timing/user and ships a
          usage-log entry to EVENTS asynchronously.
'''
import asyncio
import decimal
import enum
import inspect
import json
import time
from datetime import date, datetime
from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple

import requests
from fastapi import HTTPException, Request
from pydantic import BaseModel

from services.environment import load_and_validate_env_vars
from services.logger_config import custom_logger as logger


# --- Configuration ---------------------------------------------------------

_ENV_VARS = load_and_validate_env_vars(
    env_vars = {},
    optional_env_vars = {'EVENTS_SERVICE_URL': str}
)

EVENTS_SERVICE_URL: Optional[str] = _ENV_VARS.get('EVENTS_SERVICE_URL') or None
EVENTS_AUDIT_URL: Optional[str] = (
    f'{EVENTS_SERVICE_URL}/v1/events/audit' if EVENTS_SERVICE_URL else None
)
EVENTS_LOG_URL: Optional[str] = (
    f'{EVENTS_SERVICE_URL}/v1/events/usage-log' if EVENTS_SERVICE_URL else None
)

REQUEST_TIMEOUT_SECONDS = 10


# --- JSON encoder ----------------------------------------------------------

class _SmartJSONEncoder(json.JSONEncoder):
    '''
        Handles datetime, Decimal, Pydantic models and Enums so audit / log
        payloads can serialize the Dynamo TypedDict items without surprises.
    '''
    def default(self, o):
        if isinstance(o, (date, datetime)):
            return o.isoformat()
        if isinstance(o, decimal.Decimal):
            return float(o)
        if isinstance(o, BaseModel):
            return o.model_dump()
        if isinstance(o, enum.Enum):
            return o.value
        return super().default(o)


# --- HTTP helper -----------------------------------------------------------

def _perform_request(method: str, url: str, payload: dict) -> Optional[requests.Response]:
    '''
        Synchronous HTTP call wrapped to be safe to schedule from asyncio tasks.
    '''
    try:
        if method.upper() == 'POST':
            return requests.post(
                url, json = payload, timeout = REQUEST_TIMEOUT_SECONDS
            )
        return None
    except requests.exceptions.RequestException as e:
        error_msg = f'EVENTS request {method} {url} failed: {e}'
        logger.warning(error_msg)
        return None


async def send_audit_event(audit_data: dict) -> None:
    '''
        Fires an audit POST to the EVENTS microservice. Failures are logged but
        never raised so a downstream outage cannot break the caller.
    '''
    if not EVENTS_AUDIT_URL:
        logger.warning('EVENTS_SERVICE_URL is not set. Cannot send audit event.')
        return
    response = await asyncio.to_thread(
        _perform_request, 'POST', EVENTS_AUDIT_URL, audit_data
    )
    if response is None:
        return
    if response.status_code >= 400:
        error_msg = (
            f'Audit event rejected with status {response.status_code}: '
            f'{response.text[:200]}'
        )
        logger.warning(error_msg)
        return
    message = f'Audit event sent. Status: {response.status_code}'
    logger.info(message)


async def send_usage_log(log_data: dict) -> None:
    '''
        Fires a usage-log POST to the EVENTS microservice. Same fail-quiet
        contract as `send_audit_event`.
    '''
    if not EVENTS_LOG_URL:
        logger.warning('EVENTS_SERVICE_URL is not set. Cannot send usage log.')
        return
    response = await asyncio.to_thread(
        _perform_request, 'POST', EVENTS_LOG_URL, log_data
    )
    if response is None:
        return
    if response.status_code >= 400:
        error_msg = (
            f'Usage log rejected with status {response.status_code}: '
            f'{response.text[:200]}'
        )
        logger.warning(error_msg)
        return
    message = f'Usage log sent. Status: {response.status_code}'
    logger.info(message)


# --- Audit decorator -------------------------------------------------------

def _resolve_entity_id_and_values(
    result: Any
) -> Tuple[str, Optional[Any]]:
    '''
        Extracts (entity_id, new_values) from the wrapped function result.

        Conventions:
            - Pydantic BaseModel  → entity_id = first non-None of `id`,
              `dataset_id`, `run_id`, `client_id`; new_values = `model_dump()`.
            - Dict                → same lookup, dict itself as new_values.
            - Otherwise           → entity_id = '0' (audit service requires a
              string), new_values = None.
    '''
    candidate_keys = ('id', 'dataset_id', 'run_id', 'client_id')

    def _pick_id(values: Dict[str, Any]) -> Optional[str]:
        for key in candidate_keys:
            if key in values and values[key] is not None:
                return str(values[key])
        return None

    if isinstance(result, BaseModel):
        dumped = result.model_dump()
        return _pick_id(dumped) or '0', dumped
    if isinstance(result, dict):
        return _pick_id(result) or '0', result
    if isinstance(result, list):
        # Bulk operations: collapse to count, no specific entity_id.
        return '0', [item.model_dump() if isinstance(item, BaseModel) else item
                     for item in result]
    return '0', None


def audit_event(microservice_name: str, entity_name: str, action: str):
    '''
        Decorator factory that emits an audit event after the wrapped service
        function completes successfully. Works on both sync and async callables.
    '''
    def decorator(func: Callable):
        is_coroutine = inspect.iscoroutinefunction(func)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            _schedule_audit(result, kwargs, microservice_name, entity_name, action)
            return result

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            _schedule_audit(result, kwargs, microservice_name, entity_name, action)
            return result

        return async_wrapper if is_coroutine else sync_wrapper
    return decorator


def _schedule_audit(
    result: Any,
    kwargs: Dict[str, Any],
    microservice_name: str,
    entity_name: str,
    action: str
) -> None:
    '''
        Builds the audit payload and schedules `send_audit_event` without
        blocking the caller.
    '''
    user_id = kwargs.get('current_user') or kwargs.get('user_id') or '1001'
    entity_id, new_values = _resolve_entity_id_and_values(result)
    formatted_new = (
        json.dumps(new_values, cls = _SmartJSONEncoder) if new_values is not None else None
    )
    audit_payload = {
        'microservice': microservice_name,
        'entity_name': entity_name,
        'entity_id': entity_id,
        'action': action,
        'user_id': str(user_id),
        'old_values': None,
        'new_values': formatted_new
    }
    _safe_schedule(send_audit_event(audit_payload))


def _safe_schedule(coro) -> None:
    '''
        Schedules a coroutine on the running event loop; falls back to a
        throw-away loop when called from sync context (Lambda handler runs
        endpoints inside an event loop, so the fallback should be rare).
    '''
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        try:
            asyncio.run(coro)
        except RuntimeError as e:
            logger.warning(f'Could not schedule background task: {e}')


# --- Usage log decorator ---------------------------------------------------

def _serialize_response(response_data: Any) -> Any:
    '''
        Coerces the response into a JSON-serializable shape for the log.
    '''
    if isinstance(response_data, BaseModel):
        return response_data.model_dump()
    if isinstance(response_data, list):
        return [_serialize_response(item) for item in response_data]
    if isinstance(response_data, dict):
        return response_data
    return response_data


async def _read_request_body(request: Optional[Request]) -> Optional[Dict[str, Any]]:
    '''
        Best-effort capture of the request body for the log. Skips file uploads
        (multipart) and unknown content types to keep the payload small.
    '''
    if not request or request.method not in ('POST', 'PUT', 'PATCH'):
        return None
    content_type = request.headers.get('content-type', '') or ''
    if 'application/json' in content_type:
        try:
            return await request.json()
        except ValueError:
            return {'detail': 'Invalid JSON in request body'}
    if 'multipart/form-data' in content_type:
        return {'detail': 'Multipart form data (file upload) not logged.'}
    return {'detail': f'Content-Type {content_type} not logged.'}


def log_usage(microservice_name: str):
    '''
        Decorator factory for FastAPI route handlers. Captures method, path,
        status, IP, user, request body, response shape and elapsed ms; ships
        the entry to EVENTS asynchronously and never blocks the response.
    '''
    def decorator(func: Callable):
        is_coroutine = inspect.iscoroutinefunction(func)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            request: Optional[Request] = kwargs.get('request')
            current_user: Optional[str] = kwargs.get('current_user')
            start_time = time.perf_counter()
            status_code = 500
            response_data: Any = None
            try:
                response_data = (
                    await func(*args, **kwargs) if is_coroutine else func(*args, **kwargs)
                )
                status_code = 200
                return response_data
            except HTTPException as exc:
                status_code = exc.status_code
                response_data = {'detail': exc.detail}
                raise
            except Exception as exc:
                status_code = 500
                response_data = {'detail': str(exc)}
                raise
            finally:
                if request is not None and EVENTS_LOG_URL:
                    request_body = await _read_request_body(request)
                    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
                    log_payload = {
                        'microservice': microservice_name,
                        'endpoint': request.url.path,
                        'method': request.method,
                        'status_code': status_code,
                        'ip_address': getattr(request.client, 'host', '0.0.0.0'),
                        'user_app': current_user or 'anonymous',
                        'request_body': request_body,
                        'response_body': _serialize_response(response_data),
                        'response_time_ms': elapsed_ms
                    }
                    try:
                        encoded = json.loads(
                            json.dumps(log_payload, cls = _SmartJSONEncoder)
                        )
                        _safe_schedule(send_usage_log(encoded))
                    except (TypeError, ValueError) as serialization_error:
                        error_msg = f'Error serializing log data: {serialization_error}'
                        logger.warning(error_msg)

        return async_wrapper
    return decorator
