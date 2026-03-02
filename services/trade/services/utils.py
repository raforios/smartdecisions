'''
    Utils service
'''

import mimetypes
import time
import decimal
import asyncio
import json
import enum
from datetime import date, datetime
from zoneinfo import ZoneInfo
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type, Tuple
import requests as req
from fastapi import HTTPException, Request, UploadFile, status


from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.inspection import inspect as sa_inspect
from services.logger_config import custom_logger as logger
from services.exceptions import (
    InvalidInputError,
    RegisterAlreadyExistsError,
    RegisterNotFoundError,
    ResourceNotFoundError,
    ServiceUnavailableError
)

from services.environment import load_and_validate_env_vars

# Carga las variables de entorno necesarias
ENV_VARS = load_and_validate_env_vars(
    {
        'EVENTS_SERVICE_URL': str,
        'FILES_SERVICE_URL': str,
        'BUCKET_NAME': str,
        'TARGET_TIMEZONE': str
    },
        optional_env_vars = {
        'BUCKET_PATH': str
    }
)

EVENTS_SERVICE_URL = ENV_VARS['EVENTS_SERVICE_URL']
FILES_SERVICE_URL = ENV_VARS['FILES_SERVICE_URL']
TARGET_TIMEZONE = ENV_VARS['TARGET_TIMEZONE']
BUCKET_NAME = ENV_VARS['BUCKET_NAME']
BUCKET_PATH = ENV_VARS['BUCKET_PATH']
EVENTS_AUDIT_URL = f'{EVENTS_SERVICE_URL}/v1/events/audit' if EVENTS_SERVICE_URL else None
EVENTS_LOG_URL = f'{EVENTS_SERVICE_URL}/v1/events/usage-log' if EVENTS_SERVICE_URL else None


if FILES_SERVICE_URL:
    UPLOAD_ENDPOINT = f'{FILES_SERVICE_URL}/v1/s3/upload'


def get_current_time_gmt() -> datetime:
    '''
        Returns the current datetime object aware of the target timezone.
        This function should be used as the default value for all SQLAlchemy
        DateTime columns to ensure database consistency.
    '''
    tz = ZoneInfo(TARGET_TIMEZONE)
    return datetime.now(tz = tz)

def sqlalchemy_object_as_dict(obj):
    '''
        Helper function to serialize a SQLAlchemy object to a dictionary,
        converting complex types like datetime and Decimal to simple types.
    '''
    data = {}
    for c in sa_inspect(obj).mapper.column_attrs:
        value = getattr(obj, c.key)

        if isinstance(value, (date, datetime)):
            data[c.key] = value.isoformat()
        elif isinstance(value, decimal.Decimal):
            data[c.key] = float(value)
        else:
            data[c.key] = value

    return data

async def _perform_request(
    method: str,
    url: str,
    headers: Dict[str, str],
    payload: Optional[Dict[str, Any]] = None,
    files: Optional[Dict[str, Any]] = None
):
    '''
        Helper function to perform a request call in a thread pool executor.
    '''
    try:
        def request_call():
            if method == 'GET':
                return req.get(url, headers = headers, timeout = 600)

            if method == 'POST':
                if files:
                    return req.post(
                        url,
                        data = payload,
                        files = files,
                        headers = headers,
                        timeout = 600
                    )

                return req.post(url, json = payload, headers = headers, timeout = 600)

            if method == 'DELETE':
                return req.delete(url, json = payload, headers = headers, timeout = 600)

            raise ValueError(f'Unsupported method: {method}')

        return await asyncio.to_thread(request_call)

    except req.exceptions.RequestException as e:
        error_msg = f'An error occurred while using _perform_request function: {e}'
        logger.error(error_msg, exc_info = True)

class CustomJSONEncoder(json.JSONEncoder):
    '''
        JSON encoder to handle date and datetime objects, Pydantic models, and custom Enums.
    '''
    def default(self, o):
        if isinstance(o, (date, datetime)):
            return o.isoformat()
        if isinstance(o, BaseModel):
            return o.model_dump()
        if isinstance(o, decimal.Decimal):
            return float(o)
        if isinstance(o, enum.Enum): # New condition for Enums
            return o.value
        return super().default(o)

class UsageLogData(BaseModel):
    '''
        Data class to manage the structure of the LOGS table.
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

async def _process_and_send_usage_log(
    log_data: UsageLogData
):
    '''
       Processes and sends a usage log to the event service.
    '''
    try:
        if isinstance(log_data.response_body, int):
            log_data.response_body = {
                'message': f'Register with ID: {log_data.response_body} deleted successfully.'
            }

        log_data_json = json.dumps(log_data.model_dump(by_alias = True),
                                   cls = CustomJSONEncoder)
        asyncio.create_task(send_usage_log(json.loads(log_data_json)))
    except (TypeError) as e:
        error_msg = f'Error serializing log data: {e}'
        logger.error(error_msg, exc_info = True)

async def _get_request_body_for_logging(request: Request) -> dict | None:
    '''
        Helper to safely extract the request body for logging,
        handling different content types.
    '''
    if not request or request.method not in ['POST', 'PUT', 'PATCH']:
        return None

    content_type = request.headers.get('content-type', '')

    if 'application/json' in content_type:
        try:
            return await request.json()
        except ValueError:
            return {'detail': 'Invalid JSON in request body'}

    if 'multipart/form-data' in content_type:
        return {'detail': 'Multipart form data (file upload) not logged.'}

    return {'detail': f'Content-Type {content_type} not logged.'}

# pylint: disable=too-many-arguments, too-many-positional-arguments
async def _finalize_and_log(
    request: Request,
    microservice_name: str,
    status_code: int,
    response_data: Any,
    start_time: float,
    current_user: Optional[str],
    with_log: bool = True
):
    '''
        Helper function to handle final logging operations to reduce complexity
        in the main decorator.
    '''
    if request and EVENTS_LOG_URL:
        end_time = time.perf_counter()
        user_app = current_user if current_user else 'anonymous'
        request_body = await _get_request_body_for_logging(request)

        log_data = UsageLogData(
            microservice = microservice_name,
            endpoint = request.url.path,
            method = request.method,
            status_code = status_code,
            ip_address = request.client.host,
            user_app = user_app,
            request_body = request_body,
            response_time_ms = int((end_time - start_time) * 1000)
        )

        if with_log:
            if isinstance(response_data, list) and all(isinstance(item,
                                                BaseModel) for item in response_data):
                log_data.response_body = [item.model_dump() for item in response_data]
            elif isinstance(response_data, BaseModel):
                log_data.response_body = response_data.model_dump()
            elif isinstance(response_data, dict) and 'detail' in response_data:
                # If response_data is already a dict with 'detail', use it as is
                log_data.response_body = response_data
            else:
                log_data.response_body = response_data
        else:
            log_data.response_body = None

        await _process_and_send_usage_log(log_data)

def _handle_exception(
    e: Exception,
    db: Optional[Session] = None,
    func_name: str = 'unknown_function'
) -> Tuple[int, Any]:
    '''
        Helper to handle various exceptions, log them, and return appropriate status code
        and detail for HTTPException.
    '''
    status_code: int
    detail: Any

    if isinstance(e, SQLAlchemyError):
        if db:
            db.rollback()
        error_msg = f'Database error in {func_name}: {e}'
        logger.error(error_msg, exc_info=True)
        status_code = 500
        detail = str(e)
    elif isinstance(e, RegisterNotFoundError):
        status_code = 404
        detail = str(e)
    elif isinstance(e, (InvalidInputError, RegisterAlreadyExistsError)):
        status_code = 400
        detail = str(e)
    elif isinstance(e, HTTPException):
        status_code = e.status_code
        detail = e.detail
    elif isinstance(e, ValidationError):
        status_code = 422
        detail = json.loads(e.json())
    else:
        error_msg = f'Unexpected error in {func_name}: {e}'
        logger.error(error_msg, exc_info=True)
        status_code = 500
        detail = f'Internal Server Error: {e}'

    return status_code, detail

def handle_service_errors(microservice_name: str, with_log: bool = True):
    '''
        Decorator factory to handle common exceptions and log usage metrics.
    '''
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            db: Session = kwargs.get('db')
            request: Request = kwargs.get('request')
            current_user: Optional[str] = kwargs.get('current_user')

            start_time = time.perf_counter()
            response_data = None
            status_code = 500

            try:
                result = await func(*args, **kwargs)
                response_data = result
                status_code = 200
                return result
            except Exception as e:
                # Use the helper to determine status code and detail
                status_code, detail = _handle_exception(e, db, func.__name__)
                response_data = {'detail': detail} # Standardize response_data for errors
                raise HTTPException(status_code = status_code, detail = detail) from e
            finally:
                # Always log, regardless of success or failure
                # Make sure response_data is properly formatted before sending to _finalize_and_log
                # If an exception was raised, response_data will be {'detail': detail}
                # If successful, response_data will be the actual result
                await _finalize_and_log(
                    request = request,
                    microservice_name = microservice_name,
                    status_code = status_code,
                    response_data = response_data,
                    start_time = start_time,
                    current_user = current_user,
                    with_log = with_log
                )

        return wrapper
    return decorator

def _resolve_audit_data(final_result: Any, new_values: Any) -> Tuple[Any, Any]:
    '''
        Helper to resolve entity_id and new_values for the audit decorator,
        reducing cyclomatic complexity.
    '''
    entity_id = None

    # Resolve new_values if not provided
    if new_values is None:
        if isinstance(final_result, list):
            calculated_new_values = []
            for item in final_result:
                if isinstance(item, BaseModel):
                    calculated_new_values.append(item.model_dump())
                elif hasattr(item, '__dict__'):
                    calculated_new_values.append(sqlalchemy_object_as_dict(item))
            new_values = calculated_new_values

        elif final_result:
            if isinstance(final_result, BaseModel):
                new_values = final_result.model_dump()
            elif hasattr(final_result, '__dict__'):
                new_values = sqlalchemy_object_as_dict(final_result)

    # Resolve entity_id
    if not isinstance(final_result, list):
        if isinstance(final_result, (BaseModel, int)):
            entity_id = final_result.id if isinstance(final_result, BaseModel) \
            else final_result
        elif hasattr(final_result, 'id'):
            entity_id = final_result.id

    return entity_id, new_values

def audit_event(
    microservice_name: str,
    entity_name: str,
    action: str
):
    '''
        Decorator factory to send an audit event after a service function call.
    '''
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # The current_user/user_id is often an email or a string identifier.
            # Do not force conversion to int to avoid errors in the audit service.
            user_id = kwargs.get('current_user') or kwargs.get('user_id', '1001')

            result = await func(*args, **kwargs)

            if isinstance(result, tuple) and len(result) == 2:
                final_result, auditable_data = result
            else:
                final_result = result
                auditable_data = {
                    'old_values': None,
                    'new_values': None
                }

            old_values = auditable_data.get('old_values')
            new_values = auditable_data.get('new_values')

            # Use helper to determine IDs and values to avoid branching here
            entity_id, new_values = _resolve_audit_data(final_result, new_values)

            # Ensure entity_id is a string to satisfy the audit service schema.
            # If entity_id is None, use "0" as a safe default.
            str_entity_id = str(entity_id) if entity_id is not None else "0"

            # Ensure old_values and new_values are strings (JSON) if they are not None
            # to comply with the audit service's expected format.
            formatted_old = json.dumps(old_values, cls = CustomJSONEncoder
                            ) if old_values is not None else None
            formatted_new = json.dumps(new_values, cls = CustomJSONEncoder
                            ) if new_values is not None else None

            audit_event_data = {
                'microservice': microservice_name,
                'entity_name': entity_name,
                'entity_id': str_entity_id,
                'action': action,
                'user_id': str(user_id),
                'old_values': formatted_old,
                'new_values': formatted_new
            }
            try:
                data_to_send = json.loads(json.dumps(audit_event_data, cls = CustomJSONEncoder))
                asyncio.create_task(send_audit_event(data_to_send))
            except (TypeError, AttributeError) as e:
                error_msg = f'Error serializing audit data: {e}'
                logger.error(error_msg, exc_info = True)

            return final_result
        return wrapper
    return decorator

async def send_audit_event(audit_data: dict):
    '''
        Asynchronous function to send an audit event to the EVENTS microservice.
    '''
    if not EVENTS_AUDIT_URL:
        logger.warning('EVENTS_SERVICE_URL is not set. Cannot send audit event.')
        return

    url = EVENTS_AUDIT_URL
    response = await _perform_request('POST', url, headers = {}, payload = audit_data)
    response.raise_for_status()
    message = f'Audit event sent successfully. Status: {response.status_code}'
    logger.info(message)

async def send_usage_log(log_data: dict):
    '''
        Asynchronous function to send a usage log to the EVENTS microservice.
    '''
    if not EVENTS_LOG_URL:
        logger.warning('EVENTS_SERVICE_URL is not set. Cannot send usage log.')
        return

    url = EVENTS_LOG_URL
    response = await _perform_request('POST', url, headers = {}, payload = log_data)
    response.raise_for_status()
    message = f'Usage log sent successfully. Status: {response.status_code}'
    logger.info(message)

# --- Helper functions for file actions ---

async def _execute_file_read(
    file_name: str,
    auth_token: str,
    delimiter: Optional[str]
) -> str:
    query_string = f'?delimiter={delimiter}' if delimiter else ''
    url = f'{FILES_SERVICE_URL}/v1/s3/read/{BUCKET_NAME}/{file_name}{query_string}'
    headers = {
        'Authorization': f'{auth_token}',
        'Content-Type': 'application/json'
    }
    response = await _perform_request('GET', url, headers)
    response.raise_for_status()
    return response.text

async def _execute_file_create(
    uploaded_file: UploadFile,
    auth_token: str,
    dynamic_path: Optional[str]
) -> dict:
    upload_endpoint = f'{FILES_SERVICE_URL}/v1/s3/upload'

    mime_type, _ = mimetypes.guess_type(uploaded_file.filename)
    if not mime_type:
        mime_type = 'application/octet-stream'

    file_content_bytes = await uploaded_file.read()

    headers = {
        'Authorization': f'{auth_token}'
    }

    path_to_use = dynamic_path or BUCKET_PATH

    if path_to_use and not path_to_use.endswith('/'):
        path_to_use += '/'

    response = await _perform_request(
        method = 'POST',
        url = upload_endpoint,
        headers = headers,
        payload = {
            'bucket_name': BUCKET_NAME,
            'file_path': path_to_use if path_to_use else BUCKET_PATH
        },
        files = {
            'file': (uploaded_file.filename, file_content_bytes, mime_type)
        }
    )

    response.raise_for_status()
    return response.json()

async def _execute_file_delete(
    file_name: str,
    auth_token: str
) -> None:
    url = f'{FILES_SERVICE_URL}/v1/s3/delete'
    headers = {
        'Authorization': f'{auth_token}',
        'Content-Type': 'application/json'
    }
    payload = {
        'bucket_name': BUCKET_NAME,
        'file_name': file_name,
        'file_path': BUCKET_PATH
    }
    response = await _perform_request('DELETE', url, headers, payload)
    response.raise_for_status()
    message = f'File {file_name} successfully deleted from FILES service.'
    logger.info(message)


async def _handle_files_service(
    action: str,
    **kwargs
) -> Optional[str]:
    '''
        Handles communication with the FILES microservice using kwargs to avoid
        too many positional arguments.
        Expected kwargs per action:
        - read: file_name, auth_token, delimiter
        - create: uploaded_file, auth_token, dynamic_path
        - delete: file_name, auth_token
    '''
    try:
        if not FILES_SERVICE_URL or not BUCKET_NAME:
            raise ServiceUnavailableError(
                detail = 'FILES_SERVICE_URL or BUCKET_NAME environment variables are not set.'
            )

        if action == 'read':
            return await _execute_file_read(
                kwargs.get('file_name'),
                kwargs.get('auth_token'),
                kwargs.get('delimiter')
            )

        if action == 'create':
            return await _execute_file_create(
                kwargs.get('uploaded_file'),
                kwargs.get('auth_token'),
                kwargs.get('dynamic_path')
            )

        if action == 'delete':
            return await _execute_file_delete(
                kwargs.get('file_name'),
                kwargs.get('auth_token')
            )

        raise ValueError(f'Invalid action: {action}')
    except req.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            raise ResourceNotFoundError(
                detail = f'File \'{kwargs.get('file_name', 'unknown')}\' not found.'
            ) from e
        raise ServiceUnavailableError(
            detail = f'Failed to communicate with FILES microservice: {e}'
        ) from e
    except Exception as e:
        raise ServiceUnavailableError(
            detail = f'Unexpected error during file communication with FILES service: {e}'
        ) from e

async def _read_and_parse_file_content(
    file_name: str,
    auth_token: str,
    delimiter: Optional[str] = ','
) -> List[Dict[str, Any]]:
    '''
        Reads and parses the file content from the FILES microservice.
    '''
    file_content = await _handle_files_service(
        action = 'read',
        file_name = file_name,
        auth_token = auth_token,
        delimiter = delimiter
    )
    if not file_content:
        raise InvalidInputError(
            detail = 'File content is empty or could not be retrieved.'
        )
    try:
        file_data = json.loads(file_content)
        return file_data.get('data', [])
    except json.JSONDecodeError as e:
        raise InvalidInputError(
            detail = f'Invalid JSON format in file content. Error: {e}'
        ) from e

# pylint: disable=too-many-arguments, too-many-positional-arguments
async def perform_bulk_upload(
    db: Session,
    file_name: str,
    auth_token: str,
    bulk_schema: BaseModel,
    processor_func: Callable,
    inserter_func: Callable,
    delimiter: Optional[str] = ','
) -> Dict[str, Any]:
    '''
        Generic bulk upload processor.
    '''
    rows = await _read_and_parse_file_content(file_name, auth_token, delimiter)

    if not rows:
        return {'message': 'No valid data found in the file.',
                'created_records': 0}

    processed_data = processor_func(rows, bulk_schema)

    if not processed_data:
        raise InvalidInputError('The processed data is empty.')

    stats = await inserter_func(db, processed_data, file_name, auth_token)

    db.commit()

    await _handle_files_service(
        action = 'delete',
        file_name = file_name,
        auth_token = auth_token
    )

    return {
        'message': 'Bulk upload successful.',
        **stats
    }

def generic_bulk_processor(
    rows: List[Dict[str, Any]],
    bulk_schema: Type[BaseModel]
) -> List[BaseModel]:
    '''
        Generic processor function to validate raw data against the bulk schema.
        Pre-processes specific fields to ensure correct string typing before validation.
        Validates row-by-row, logging warnings for invalid data, and returns
        a list of valid Pydantic objects.
    '''
    processed_data = []
    for row in rows:
        # Pre-process row to ensure problematic fields are strings
        processed_row = row.copy() # Work on a copy to not modify original row during iteration
        for key in ['code', 'external_code', 'contact_phone']:
            if key in processed_row and not isinstance(processed_row[key], str):
                processed_row[key] = str(processed_row[key])
        try:
            # Pydantic validation of the processed_row against the expected schema
            processed_data.append(bulk_schema.model_validate(processed_row))

        except ValidationError as e:
            error_msg = f'Skipping invalid row during bulk processing: {processed_row}. Error: {e}'
            logger.warning(error_msg)
            # Continues processing the rest of the list
            continue

    return processed_data

def _trigger_bulk_audit(
    microservice: str,
    entity: str,
    user: str,
    result: dict
):
    ''' Helper to trigger async audit for bulk ops '''
    audit_data = {
        'microservice': microservice,
        'entity_name': entity,
        'entity_id': 0,
        'action': 'BULK_CREATE',
        'user_id': user,
        'old_values': None,
        'new_values': json.dumps(result)
    }
    asyncio.create_task(send_audit_event(audit_data))

async def _execute_bulk_logic( # pylint: disable=too-many-arguments
    service_func: Callable,
    db: Session,
    file_name: str,
    delimiter: str,
    auth_token: str
):
    '''
        Helper to execute the service call and catch specific exceptions,
        returning result and status code to avoid branching in main wrapper.
    '''
    try:
        res = await service_func(
            db = db,
            file_name = file_name,
            delimiter = delimiter,
            auth_token = auth_token
        )
        return res, status.HTTP_201_CREATED
    except HTTPException as e:
        return {'detail': str(e.detail)}, e.status_code

# pylint: disable=too-many-arguments, too-many-locals
async def generic_bulk_controller_wrapper(
    db: Session,
    request: Request,
    current_user: str,
    file_name: str,
    microservice_name: str,
    entity_name: str,
    service_func: Callable,
    delimiter: Optional[str] = ',',
    auth_token: Optional[str] = None
) -> Dict[str, Any]:
    '''
        Generic controller wrapper for bulk upload endpoints.
        Handles logging, status tracking, audit event generation, and usage logging.
    '''
    start_time = time.perf_counter()

    # 1. Execute logic securely via helper
    result, status_code = await _execute_bulk_logic(
        service_func, db, file_name, delimiter, auth_token
    )

    # 2. Audit (only on success)
    if status_code < 400:
        _trigger_bulk_audit(microservice_name, entity_name, current_user, result)

    # 3. Usage Log
    await _finalize_and_log(
        request, microservice_name, status_code, result, start_time, current_user
    )

    # 4. Return result or raise error
    if status_code >= 400:
        raise HTTPException(status_code = status_code, detail = result['detail'])

    return result
