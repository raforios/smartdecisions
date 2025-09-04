'''
    Utils service
'''

import os
import time
import asyncio
import json
from datetime import date, datetime
from functools import wraps
import httpx
from dotenv import dotenv_values
from fastapi import HTTPException, Request

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, NoInspectionAvailable
from sqlalchemy.inspection import inspect as sa_inspect
from services.logger_config import custom_logger as logger
from services.exceptions import (
    InvalidInputError,
    RegisterAlreadyExistsError,
    RegisterNotFoundError
)

_LOCAL_ENV_PARAMS = dotenv_values('.env') if os.path.exists('.env') else {}
EVENTS_SERVICE_URL = os.environ.get('EVENTS_SERVICE_URL') or \
                        _LOCAL_ENV_PARAMS.get('EVENTS_SERVICE_URL')
EVENTS_AUDIT_URL = None
EVENTS_LOG_URL = None

if EVENTS_SERVICE_URL:
    EVENTS_AUDIT_URL = f'{EVENTS_SERVICE_URL}/v1/events/audit'
    EVENTS_LOG_URL = f'{EVENTS_SERVICE_URL}/v1/events/usage-log'

class CustomJSONEncoder(json.JSONEncoder):
    '''
        JSON encoder to handle date and datetime objects.
    '''
    def default(self, o):
        if isinstance(o, (date, datetime)):
            return o.isoformat()
        return super().default(o)

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
                logger.error(error_msg, exc_info=True)
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
                    status_code=422,
                    detail=json.loads(e.json())
                ) from e
            finally:
                end_time = time.perf_counter()
                if request and EVENTS_LOG_URL:
                    log_data = {
                        'microservice': microservice_name,
                        'endpoint': request.url.path,
                        'method': request.method,
                        'status_code': status_code,
                        'ip_address': request.client.host,
                        'user_id': kwargs.get('current_user') if 'current_user' in kwargs\
                            else 'anonymous',
                        'request_body': request_body,
                        # 'response_body': response_data.model_dump() if isinstance(
                        #     response_data, BaseModel) else response_data,
                        'response_body': response_data,
                        'response_time_ms': int((end_time - start_time) * 1000)
                    }
                    try:
                        if isinstance(response_data, list) and all(
                            isinstance(item, BaseModel) for item in response_data):
                            log_data['response_body'] = [
                                item.model_dump() for item in response_data]
                        elif isinstance(response_data, BaseModel):
                            log_data['response_body'] = response_data.model_dump()

                        log_data_json = json.dumps(log_data, cls = CustomJSONEncoder)
                        asyncio.create_task(send_usage_log(json.loads(log_data_json)))
                    except Exception as e:
                        error_msg = f'Error serializing log data: {e}'
                        logger.error(error_msg, exc_info = True)
        return wrapper
    return decorator


def audit_event(
    microservice_name: str,
    entity_name: str,
    action: str,
    response_schema: BaseModel = None,
    entity_id_field: str = 'id'
):
    '''
        Decorator factory to send an audit event after a service function call.
    '''
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user_id = kwargs.get('user_id', 'usr_test')

            result = await func(*args, **kwargs)
            old_values = kwargs.get('old_values', None)
            auditable_result = None

            if response_schema:
                # Lógica para CREATE y UPDATE, sin cambios.
                if isinstance(result, BaseModel):
                    auditable_result = result
                else:
                    try:
                        state = sa_inspect(result)
                        auditable_dict = {
                            attr.key: getattr(result, attr.key)
                            for attr in state.mapper.column_attrs
                        }
                    except NoInspectionAvailable:
                        auditable_dict = result.__dict__

                    if user_id:
                        auditable_dict['user_id'] = user_id

                    auditable_result = response_schema.model_validate(auditable_dict)
            else:
                auditable_result = {
                    'id': result,
                    'user_id': user_id
                }

            audit_event_data = {
                'microservice': microservice_name,
                'entity_name': entity_name,
                'entity_id': (
                    getattr(auditable_result, entity_id_field, None)
                    if isinstance(auditable_result, BaseModel)
                    else auditable_result.get(entity_id_field, None)
                ),
                  'action': action,
                'user_id': user_id,
                'old_values': old_values,
                'new_values': auditable_result.model_dump() if isinstance(
                    auditable_result, BaseModel) else auditable_result
            }
            try:
                data_to_send = json.loads(json.dumps(audit_event_data, cls = CustomJSONEncoder))
                asyncio.create_task(send_audit_event(data_to_send))
            except Exception as e:
                error_msg = f'Error serializing audit data: {e}'
                logger.error(error_msg, exc_info = True)

            return result
        return wrapper
    return decorator

async def send_audit_event(audit_data: dict):
    '''
        Asynchronous function to send an audit event to the EVENTS microservice.
    '''
    if not EVENTS_AUDIT_URL:
        logger.warning('EVENTS_SERVICE_URL is not set. Cannot send audit event.')
        return

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(EVENTS_AUDIT_URL, json = audit_data, timeout = 5.0)
            response.raise_for_status()
            message = f'Audit event sent successfully. Status: {response.status_code}'
            logger.info(message)
        except httpx.HTTPStatusError as e:
            error_msg = f'Error sending audit event: {e.response.status_code} - {e.response.text}'
            logger.error(error_msg, exc_info = True)
        except httpx.RequestError as e:
            error_msg = f'An error occurred while sending the audit event: {e}'
            logger.error(error_msg, exc_info = True)

async def send_usage_log(log_data: dict):
    '''
        Asynchronous function to send a usage log to the EVENTS microservice.
    '''
    if not EVENTS_LOG_URL:
        logger.warning('EVENTS_SERVICE_URL is not set. Cannot send usage log.')
        return

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(EVENTS_LOG_URL, json = log_data, timeout = 5.0)
            response.raise_for_status()
            message = f'Usage log sent successfully. Status: {response.status_code}'
            logger.info(message)
        except httpx.HTTPStatusError as e:
            error_msg = f'Error sending usage log: {e.response.status_code} - {e.response.text}'
            logger.error(error_msg, exc_info = True)
        except httpx.RequestError as e:
            error_msg = f'An error occurred while sending the usage log: {e}'
            logger.error(error_msg, exc_info = True)
