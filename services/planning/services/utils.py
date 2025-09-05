'''
    Utils service
'''

import os
import time
import asyncio
import json
from datetime import date, datetime
from functools import wraps
from typing import Any, Callable, Dict, List, Optional
import requests as req
from dotenv import dotenv_values
from fastapi import HTTPException, Request

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

_LOCAL_ENV_PARAMS = dotenv_values('.env') if os.path.exists('.env') else {}
EVENTS_SERVICE_URL = os.environ.get('EVENTS_SERVICE_URL') or \
                        _LOCAL_ENV_PARAMS.get('EVENTS_SERVICE_URL')
EVENTS_AUDIT_URL = None
EVENTS_LOG_URL = None

if EVENTS_SERVICE_URL:
    EVENTS_AUDIT_URL = f'{EVENTS_SERVICE_URL}/v1/events/audit'
    EVENTS_LOG_URL = f'{EVENTS_SERVICE_URL}/v1/events/usage-log'

def sqlalchemy_object_as_dict(obj):
    '''
        Helper function to serialize a SQLAlchemy object to a dictionary.
    '''
    return {
        c.key: getattr(obj, c.key)
        for c in sa_inspect(obj).mapper.column_attrs
    }

async def _perform_request(
    method: str,
    url: str,
    headers: Dict[str, str],
    payload: Optional[Dict[str, Any]] = None
):
    '''
        Helper function to perform a request call in a thread pool executor.
    '''
    try:
        def request_call():
            if method == 'GET':
                return req.get(url, headers = headers, timeout = 600)

            if method == 'POST':
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
        JSON encoder to handle date and datetime objects.
    '''
    def default(self, o):
        if isinstance(o, (date, datetime)):
            return o.isoformat()
        if isinstance(o, BaseModel):
            return o.model_dump()
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
            log_data.response_body =  {
                'message': f'Register with ID: {log_data.response_body} deleted successfully.'
            }

        log_data_json = json.dumps(log_data.model_dump(by_alias = True),
                                   cls = CustomJSONEncoder)
        asyncio.create_task(send_usage_log(json.loads(log_data_json)))
    except (TypeError) as e:
        error_msg = f'Error serializing log data: {e}'
        logger.error(error_msg, exc_info = True)

def handle_service_errors(microservice_name: str):
    '''
        Decorator factory to handle common exceptions and log usage metrics.
    '''
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            db: Session = kwargs.get('db')
            request: Request = kwargs.get('request')

            start_time = time.perf_counter()
            response_data = None
            status_code = 500

            request_body = None
            if request and request.method in ['POST', 'PUT', 'PATCH']:
                try:
                    request_body = await request.json()
                except ValueError:
                    request_body = {'detail': 'Invalid JSON in request body'}

            try:
                result = await func(*args, **kwargs)
                response_data = result
                status_code = 200
                return result
            except SQLAlchemyError as e:
                if db:
                    db.rollback()
                error_msg = f'Database error in {func.__name__}: {e}'
                logger.error(error_msg, exc_info = True)
                status_code = 500
                response_data = {'detail': str(e)}
                raise HTTPException(status_code = status_code, detail = str(e)) from e
            except (InvalidInputError, RegisterAlreadyExistsError, RegisterNotFoundError) as e:
                status_code = 400
                response_data = {'detail': str(e)}
                raise HTTPException(status_code = status_code, detail = str(e)) from e
            except HTTPException as e:
                status_code = e.status_code
                response_data = {'detail': e.detail}
                raise e
            except ValidationError as e:
                raise HTTPException(
                    status_code = 422,
                    detail = json.loads(e.json())
                ) from e
            finally:
                if request and EVENTS_LOG_URL:
                    end_time = time.perf_counter()
                    user_app = kwargs.get('current_user') if 'current_user' in kwargs \
                        else 'anonymous'

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

                    if isinstance(response_data, list) and all(isinstance(item,
                                                        BaseModel) for item in response_data):
                        log_data.response_body = [item.model_dump() for item in response_data]
                    elif isinstance(response_data, BaseModel):
                        log_data.response_body = response_data.model_dump()
                    else:
                        log_data.response_body = response_data

                    await _process_and_send_usage_log(log_data)

        return wrapper
    return decorator


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
            user_id = kwargs.get('user_id', 'usr_test')
            result = await func(*args, **kwargs)

            if isinstance(result, tuple) and len(result) == 2:
                final_result, auditable_data = result
            else:
                final_result = result
                auditable_data = {
                    'old_values': None,
                    'new_values': None
                }

            entity_id = None
            if isinstance(final_result, (BaseModel, int)):
                entity_id = final_result.id if isinstance(final_result, BaseModel) else final_result
            elif hasattr(final_result, 'id'):
                entity_id = final_result.id

            new_values = None
            if final_result and isinstance(final_result, BaseModel):
                new_values = final_result.model_dump()
            elif final_result and hasattr(final_result, '__dict__'):
                new_values = sqlalchemy_object_as_dict(final_result)

            audit_event_data = {
                'microservice': microservice_name,
                'entity_name': entity_name,
                'entity_id': entity_id,
                'action': action,
                'user_id': user_id,
                'old_values': auditable_data.get('old_values'),
                'new_values': new_values
            }
            try:
                data_to_send = json.loads(json.dumps(audit_event_data, cls = CustomJSONEncoder))
                asyncio.create_task(send_audit_event(data_to_send))
            except (TypeError, AttributeError) as e:
                error_msg = f'Error serializing audit data: {e}'
                logger.error(error_msg, exc_info = True)

            # Retornar el resultado final para que el controlador lo use.
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

async def _handle_files_service_logic(
    action: str,
    file_name: str,
    auth_token: str,
    delimiter: Optional[str] = None
) -> Optional[str]:
    '''
        Handles communication with the FILES microservice for reading and deleting files.
        This function standardizes file service interactions.
    '''
    try:
        files_service_url = os.environ.get('FILES_SERVICE_URL') or \
                            _LOCAL_ENV_PARAMS.get('FILES_SERVICE_URL')
        bucket_name = os.environ.get('BUCKET_NAME') or \
                      _LOCAL_ENV_PARAMS.get('BUCKET_NAME')
        bucket_path = os.environ.get('BUCKET_PATH') or \
                      _LOCAL_ENV_PARAMS.get('BUCKET_PATH')

        if not files_service_url or not bucket_name:
            raise ServiceUnavailableError(
                detail = 'FILES_SERVICE_URL or BUCKET_NAME environment variables are not set.'
            )

        headers = {
            'Authorization': f'{auth_token}',
            'Content-Type': 'application/json'
        }

        if action == 'read':
            query_string = f'?delimiter={delimiter}' if delimiter else ''
            url = f'{files_service_url}/v1/s3/read/{bucket_name}/{file_name}{query_string}'
            response = await _perform_request('GET', url, headers)
            response.raise_for_status()
            return response.text

        if action == 'delete':
            url = f'{files_service_url}/v1/s3/delete'
            payload = {
                'bucket_name': bucket_name,
                'file_name': file_name,
                'file_path': bucket_path
            }
            response = await _perform_request('DELETE', url, headers, payload)
            response.raise_for_status()
            message = f'File {file_name} successfully deleted from FILES service.'
            logger.info(message)
            return None


        raise ValueError(f'Invalid action: {action}')
    except req.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            raise ResourceNotFoundError(
                detail = f'File \'{file_name}\' not found in FILES microservice.'
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
    file_content = await _handle_files_service_logic(
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

    await _handle_files_service_logic('delete', file_name, auth_token)

    return {
        'message': 'Bulk upload successful.',
        **stats
    }
