'''
    Utils service.

    Event emission, usage logging and centralized error handling for the
    PARAMETERS microservice.

    This module is the DynamoDB-backed derivation of the canonical MySQL
    boilerplate `services/localization/services/utils.py`. The function names,
    signatures and responsibilities are kept identical so every microservice
    shares the same contract; only the storage-specific pieces are adapted:

        - SQLAlchemy `Session` / `SQLAlchemyError` handling is replaced with
          botocore `ClientError` handling (DynamoDB has no transactional
          rollback, so none is attempted).
        - The SQL-only helper `sqlalchemy_object_as_dict` and the FILES bulk
          upload helpers are dropped (analytics does not perform them).
        - `audit_event` also supports synchronous callables, because the
          DynamoDB service layer is synchronous (boto3), unlike localization's
          async SQLAlchemy services.
'''
from dataclasses import dataclass
import asyncio
from collections.abc import Callable
import decimal
import enum
import inspect
import json
import time
from datetime import date, datetime
from zoneinfo import ZoneInfo
from functools import wraps
from typing import Any

import requests as req
from fastapi import HTTPException, Request
from jose import JWTError, jwt
from pydantic import BaseModel, ValidationError
from botocore.exceptions import ClientError as AWSClientError

from services.logger_config import custom_logger as logger
from services.exceptions import (
    InvalidInputError,
    RegisterAlreadyExistsError,
    RegisterNotFoundError
)
from services.environment import load_and_validate_env_vars

# Loads the environment variables this module needs
ENV_VARS = load_and_validate_env_vars(
    env_vars = {
        'TARGET_TIMEZONE': str,
        'REQUEST_TIMEOUT_SECONDS': int
    },
    optional_env_vars = {
        'API_URL': str
    }
)

TARGET_TIMEZONE = ENV_VARS['TARGET_TIMEZONE']
# One address for every service: the gateway api.bearsoft.com.bo routes each
# /v1/<service> to its own Lambda, so the path names the service, not the URL.
API_URL = (ENV_VARS.get('API_URL') or '').rstrip('/') or None
EVENTS_AUDIT_URL = f'{API_URL}/v1/events/audit' if API_URL else None
EVENTS_LOG_URL = f'{API_URL}/v1/events/usage-log' if API_URL else None

REQUEST_TIMEOUT_SECONDS = ENV_VARS['REQUEST_TIMEOUT_SECONDS']


def get_current_time_gmt() -> datetime:
    '''
        Returns the current datetime object aware of the target timezone.
        This function should be used as the default value for all timestamp
        attributes to ensure database consistency.
    '''
    tz = ZoneInfo(TARGET_TIMEZONE)
    return datetime.now(tz = tz)


def process_query_params(query_params: Any) -> dict[str, Any]:
    '''
        Processes query parameters from a Pydantic model or dictionary into a
        dictionary for DynamoDB queries. Prefers Pydantic V2's `model_dump()`
        and falls back to V1's `dict()` for backwards compatibility.
    '''
    if hasattr(query_params, 'model_dump'):
        return query_params.model_dump(exclude_none = True)
    if hasattr(query_params, 'dict'):
        return query_params.dict(exclude_none = True)
    return query_params


class CustomJSONEncoder(json.JSONEncoder):
    '''
        JSON encoder to handle datetime, Decimal, Pydantic models and Enums so
        audit / usage-log payloads serialize DynamoDB items without surprises.
    '''
    def default(
        self,
        o
    ):
        if isinstance(o, (date, datetime)):
            return o.isoformat()
        if isinstance(o, decimal.Decimal):
            return float(o)
        if isinstance(o, BaseModel):
            return o.model_dump()
        if isinstance(o, enum.Enum):
            return o.value
        return super().default(o)


class UsageLogData(BaseModel):
    '''
        Data class to manage the structure of the usage LOGS table.
    '''
    microservice: str
    endpoint: str
    method: str
    status_code: int
    ip_address: str
    user_app: str
    request_body: dict | None = None
    response_body: dict | list | None = None
    response_time_ms: int


async def _perform_request(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    authorization: str | None = None
) -> req.Response | None:
    '''
        Helper function to perform a request call in a thread pool executor.
        Only POST is needed to reach the EVENTS microservice. Returns None on
        transport failure so a downstream outage never breaks the caller.
    '''
    try:
        def request_call():
            if method == 'POST':
                return req.post(
                    url, json = payload, timeout = REQUEST_TIMEOUT_SECONDS,
                    headers = {'Authorization': authorization} if authorization else None
                )
            raise ValueError(f'Unsupported method: {method}')

        return await asyncio.to_thread(request_call)
    except req.exceptions.RequestException as e:
        error_msg = f'An error occurred while using _perform_request function: {e}'
        logger.error(error_msg, exc_info = True)
        return None


async def send_audit_event(
    audit_data: dict,
    authorization: str | None = None
) -> None:
    '''
        Asynchronous function to send an audit event to the EVENTS microservice.
    '''
    if not EVENTS_AUDIT_URL:
        logger.warning('API_URL is not set. Cannot send audit event.')
        return

    response = await _perform_request(
        'POST', EVENTS_AUDIT_URL, payload = audit_data, authorization = authorization
    )
    if response is None:
        return
    if response.status_code >= 400:
        error_msg = (
            f'Audit event rejected with status {response.status_code}: {response.text[:200]}'
        )
        logger.warning(error_msg)
        return
    message = f'Audit event sent successfully. Status: {response.status_code}'
    logger.info(message)


async def send_usage_log(
    log_data: dict,
    authorization: str | None = None
) -> None:
    '''
        Asynchronous function to send a usage log to the EVENTS microservice.
    '''
    if not EVENTS_LOG_URL:
        logger.warning('API_URL is not set. Cannot send usage log.')
        return

    response = await _perform_request(
        'POST', EVENTS_LOG_URL, payload = log_data, authorization = authorization
    )
    if response is None:
        return
    if response.status_code >= 400:
        error_msg = f'Usage log rejected with status {response.status_code}: {response.text[:200]}'
        logger.warning(error_msg)
        return
    message = f'Usage log sent successfully. Status: {response.status_code}'
    logger.info(message)


async def _process_and_send_usage_log(
    log_data: UsageLogData,
    authorization: str | None = None
) -> None:
    '''
        Processes and sends a usage log to the EVENTS microservice.
    '''
    try:
        if isinstance(log_data.response_body, int):
            log_data.response_body = {
                'message': f'Register with ID: {log_data.response_body} deleted successfully.'
            }

        log_data_json = json.dumps(
            log_data.model_dump(by_alias = True), cls = CustomJSONEncoder
        )
        # Awaited, not scheduled (Rafael, 19-oct-2026): Lambda freezes as soon
        # as the response leaves, and a background task could die unsent.
        await send_usage_log(json.loads(log_data_json), authorization)
    except TypeError as e:
        error_msg = f'Error serializing log data: {e}'
        logger.error(error_msg, exc_info = True)


async def _get_request_body_for_logging(request: Request | None) -> dict | None:
    '''
        Helper to safely extract the request body for logging, handling the
        different content types.
    '''
    if not request or request.method not in ['POST', 'PUT', 'PATCH']:
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


def _serialize_response(response_data: Any) -> Any:
    '''
        Coerces the response into a JSON-serializable shape for the usage log.
    '''
    if isinstance(response_data, BaseModel):
        return response_data.model_dump()
    if isinstance(response_data, list):
        return [_serialize_response(item) for item in response_data]
    return response_data


def _safe_schedule(coro) -> None:
    '''
        Schedules a coroutine on the running event loop; falls back to a
        throw-away loop when called from a sync context without a running loop.
    '''
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        try:
            asyncio.run(coro)
        except RuntimeError as e:
            error_msg = f'Could not schedule background task: {e}'
            logger.warning(error_msg)


def handle_service_errors(
    microservice_name: str,
    with_log: bool = True
):
    '''
        Decorator factory to handle common exceptions and log usage metrics.
        Applied to the controller layer, where `request` and `current_user`
        are available as keyword arguments.
    '''
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(
            *args,
            **kwargs
        ):
            request: Request = kwargs.get('request')
            start_time = time.perf_counter()
            response_data = None
            status_code = 500

            request_body = await _get_request_body_for_logging(request)

            try:
                result = await func(*args, **kwargs)
                response_data = result
                status_code = 200
                return result
            except AWSClientError as e:
                error_msg = f'AWS client error in {func.__name__}: {e}'
                logger.error(error_msg, exc_info = True)
                status_code = 500
                response_data = {'detail': 'A database client error occurred.'}
                raise HTTPException(
                    status_code = status_code,
                    detail = 'A database client error occurred.'
                ) from e
            except (InvalidInputError, RegisterAlreadyExistsError, RegisterNotFoundError) as e:
                # Our own HTTP errors already carry the right status (400/404/
                # 409) and a stable code as detail. Re-raise them intact: the
                # frontend only recognises the code when the detail is exactly
                # the code, never "409: CODE".
                status_code = e.status_code
                response_data = {'detail': e.detail}
                raise
            except HTTPException as e:
                status_code = e.status_code
                response_data = {'detail': e.detail}
                raise
            except ValidationError as e:
                status_code = 422
                response_data = {'detail': json.loads(e.json())}
                raise HTTPException(status_code = 422, detail = json.loads(e.json())) from e
            finally:
                if request and EVENTS_LOG_URL:
                    end_time = time.perf_counter()
                    log_data = UsageLogData(
                        microservice = microservice_name,
                        endpoint = request.url.path,
                        method = request.method,
                        status_code = status_code,
                        ip_address = getattr(request.client, 'host', '0.0.0.0'),
                        user_app = (_caller_email(request) or kwargs.get('current_user')
                                    or 'anonymous'),
                        request_body = request_body,
                        response_time_ms = int((end_time - start_time) * 1000)
                    )
                    log_data.response_body = (
                        _serialize_response(response_data) if with_log else None
                    )
                    await _process_and_send_usage_log(log_data, _caller_authorization(request))

        return wrapper
    return decorator


@dataclass(frozen = True)
class AuditSpec:
    '''
        What an audited call records: the service, the entity, the action and,
        when the entity is not identified by `id`, the field that identifies it.
    '''
    microservice_name: str
    entity_name: str
    action: str
    id_field: str | None = None


def _resolve_audit_entity(
    result: Any,
    id_field: str | None = None
) -> tuple[str, Any | None]:
    '''
        Extracts (entity_id, new_values) from the wrapped function result.

        The audit service requires a string entity_id, so '0' is used as a
        neutral fallback for bulk / value-less results. `id_field` names the
        field that identifies the entity (an account's `account_code`); without
        it, the usual names are tried, as before (Rafael, 22-oct-2026).
    '''
    candidate_keys = ((id_field,) if id_field else ()) + ('id', 'run_id', 'dataset_id', 'client_id')

    def _pick_id(values: dict[str, Any]) -> str:
        for key in candidate_keys:
            if values.get(key) is not None:
                return str(values[key])
        return '0'

    if isinstance(result, BaseModel):
        dumped = result.model_dump()
        return _pick_id(dumped), dumped
    if isinstance(result, dict):
        return _pick_id(result), result
    return '0', None


def _audit_payload(
    result: Any,
    kwargs: dict[str, Any],
    spec: AuditSpec
) -> dict[str, Any]:
    '''
        Builds the audit record of a call: who changed which entity, and how.
    '''
    user_id = (_caller_email(kwargs.get('request')) or kwargs.get('current_user')
               or kwargs.get('user_id') or 'usr_test')
    entity_id, new_values = _resolve_audit_entity(result, spec.id_field)
    formatted_new = (
        json.dumps(new_values, cls = CustomJSONEncoder) if new_values is not None else None
    )
    audit_payload = {
        'microservice': spec.microservice_name,
        'entity_name': spec.entity_name,
        'entity_id': entity_id,
        'action': spec.action,
        'user_id': str(user_id),
        'old_values': None,
        'new_values': formatted_new
    }
    return audit_payload


def audit_event(
    microservice_name: str,
    entity_name: str,
    action: str,
    id_field: str | None = None
):
    '''
        Decorator factory to send an audit event after a service function call.
        Supports both synchronous and asynchronous wrapped callables.
        `id_field` names the field of the result that identifies the entity.
    '''
    spec = AuditSpec(microservice_name, entity_name, action, id_field)

    def decorator(func: Callable):
        is_coroutine = inspect.iscoroutinefunction(func)

        @wraps(func)
        def sync_wrapper(
            *args,
            **kwargs
        ):
            result = func(*args, **kwargs)
            _safe_schedule(send_audit_event(
                _audit_payload(result, kwargs, spec),
                _caller_authorization(kwargs.get('request'))
            ))
            return result

        @wraps(func)
        async def async_wrapper(
            *args,
            **kwargs
        ):
            result = await func(*args, **kwargs)
            # Awaited before answering: in Lambda a scheduled task can be
            # frozen with the function and the audit record lost (19-oct-2026).
            await send_audit_event(
                _audit_payload(result, kwargs, spec),
                _caller_authorization(kwargs.get('request'))
            )
            return result

        return async_wrapper if is_coroutine else sync_wrapper
    return decorator


def _caller_authorization(request: Request | None) -> str | None:
    '''
        The Authorization header of the request being served, forwarded to
        EVENTS so it can check that whoever writes a log is a real caller.

        The token was already validated by this service; EVENTS validates it
        again because its POST endpoints are reachable from the internet.

        Args:
            request (Request | None): The incoming request, when there is one.

        Returns:
            str | None: The header, or None for calls with no request.
    '''
    return request.headers.get('authorization') if request is not None else None


def _caller_email(request: Request | None) -> str | None:
    '''
        The e-mail of whoever signed in and made the call: the person a log
        records, never the company that owns the data (Rafael, 23-oct-2026:
        by the user we know the company, not the other way round).

        The token was already validated by the route, so its claims are only
        read here, not checked again.

        Args:
            request (Request | None): The incoming request, when there is one.

        Returns:
            str | None: The e-mail in the token, or None when there is none.
    '''
    header = _caller_authorization(request) or ''
    scheme, _, token = header.partition(' ')
    if scheme.lower() != 'bearer' or not token:
        return None
    try:
        return jwt.get_unverified_claims(token).get('email')
    except JWTError:
        return None
