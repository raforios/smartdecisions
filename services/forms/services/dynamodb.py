'''
    DynamoDB Service for temporary form session management.
    Handles CRUD operations for form sessions stored in AWS DynamoDB.
'''
from decimal import Decimal
from datetime import datetime, date
from typing import Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError

from services.logger_config import custom_logger as logger
from services.exceptions import ServiceUnavailableError

from services.environment import load_and_validate_env_vars

ENV_VARS = load_and_validate_env_vars(
    {
        'DYNAMODB_REGION': str,
        'DYNAMODB_TABLE_NAME': str
    },
    optional_env_vars = {
        'DYNAMODB_ENDPOINT_URL': str
    }
)

# Configuration for DynamoDB
# These should ideally come from environment variables or a dedicated config file
# Default values provided for local development, but highly recommend environment vars.
DYNAMODB_REGION = ENV_VARS['DYNAMODB_REGION']
DYNAMODB_TABLE_NAME = ENV_VARS['DYNAMODB_TABLE_NAME']
DYNAMODB_ENDPOINT_URL = ENV_VARS['DYNAMODB_ENDPOINT_URL']


class DynamoDBClient: # pylint: disable=too-few-public-methods
    '''
        Singleton-like class to manage the DynamoDB client connection.
    '''
    _instance = None
    _table = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # pylint: disable=protected-access
            cls._instance._initialize_client()
            # pylint: enable=protected-access
        return cls._instance

    def _initialize_client(self):
        '''
            Initializes the DynamoDB client and table resource.
        '''
        try:
            message = f'''Initializing DynamoDB client for region: {DYNAMODB_REGION},
                        table: {DYNAMODB_TABLE_NAME}'''
            logger.info(message)

            resource_args = {
                'region_name': DYNAMODB_REGION
            }
            if DYNAMODB_ENDPOINT_URL:
                resource_args['endpoint_url'] = DYNAMODB_ENDPOINT_URL
                message = f'Using DynamoDB endpoint URL: {DYNAMODB_ENDPOINT_URL}'
                logger.info(message)

            # pylint: disable=W0201
            self.dynamodb = boto3.resource('dynamodb', **resource_args)
            self._table = self.dynamodb.Table(DYNAMODB_TABLE_NAME)
            # pylint: enable=W0201

            # Test connection by attempting to access a table property
            # This might not fail immediately for invalid table, but good for basic check
            _ = self._table.table_status
            message = 'DynamoDB client and table resource initialized successfully.'
            logger.info(message)
        except NoCredentialsError as e:
            error_msg = f'No AWS credentials found for DynamoDB: {e}'
            logger.error(error_msg, exc_info = True)
            raise ServiceUnavailableError(
                detail = 'AWS credentials not configured for DynamoDB.'
            ) from e
        except PartialCredentialsError as e:
            error_msg = f'Partial AWS credentials found for DynamoDB: {e}'
            logger.error(error_msg, exc_info = True)
            raise ServiceUnavailableError(
                detail = 'Incomplete AWS credentials for DynamoDB.'
            ) from e
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            if error_code == 'ResourceNotFoundException':
                error_msg = f'DynamoDB table "{DYNAMODB_TABLE_NAME}" not found: {e}'
                logger.error(error_msg, exc_info = True)
                raise ServiceUnavailableError(
                    detail = f'DynamoDB table "{DYNAMODB_TABLE_NAME}" does not exist.'
                ) from e
            error_msg = f'AWS Client Error during DynamoDB initialization: {e}'
            logger.error(error_msg, exc_info = True)
            raise ServiceUnavailableError(
                detail = f'Failed to connect to DynamoDB: {e}'
            ) from e
        except Exception as e:
            error_msg = f'Unexpected error initializing DynamoDB: {e}'
            logger.error(error_msg, exc_info = True)
            raise ServiceUnavailableError(
                detail = 'An unexpected error occurred during DynamoDB initialization.'
            ) from e

    def get_table(self):
        '''
            Returns the initialized DynamoDB table resource.
        '''
        if not self._table:
            # pylint: disable=protected-access
            self._initialize_client() # Re-initialize if for some reason it's None
            # pylint: enable=protected-access
        return self._table

def _convert_for_dynamodb(obj):
    '''
        Recursively converts datetime.datetime and datetime.date objects to ISO 
        8601 strings. Handles dictionaries and lists.
    '''
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _convert_for_dynamodb(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_for_dynamodb(elem) for elem in obj]
    return obj

# Instantiate the client once globally for the module
dynamodb_client_instance = DynamoDBClient()

async def save_session(session_data: Dict[str, Any]) -> None:
    '''
        Saves or updates a form session record in DynamoDB.

        The 'session_id' field is used as the primary key.
        The 'ttl' field must be an integer (Unix epoch timestamp) for TTL functionality.
    '''
    table = dynamodb_client_instance.get_table()

    processed_session_data = _convert_for_dynamodb(session_data)

    try:
        message = f'Attempting to save session: {session_data.get('session_id')}'
        logger.debug(message)
        response = table.put_item(Item = processed_session_data)
        message = f'''Session {session_data.get('session_id')}
                        saved successfully to DynamoDB.'''
        logger.info(message)
        message = f'DynamoDB put_item response: {response}'
        logger.debug(message)
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code')
        error_msg = f'''DynamoDB ClientError saving session
                        {session_data.get('session_id')}: {error_code} - {e}'''
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(
            detail = f'DynamoDB error saving session: {e}'
        ) from e
    except Exception as e:
        error_msg = f'''Unexpected error saving session
                        {session_data.get('session_id')} to DynamoDB: {e}'''
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(
            detail = f'An unexpected error occurred while saving session: {e}'
        ) from e

async def get_session_by_id(session_id: str) -> Optional[Dict[str, Any]]:
    '''
        Retrieves a form session record from DynamoDB by its session_id.
        Returns None if the session is not found or has expired.
    '''
    table = dynamodb_client_instance.get_table()
    try:
        message = f'Attempting to retrieve session: {session_id}'
        logger.debug(message)
        response = table.get_item(Key = {'session_id': session_id})
        item = response.get('Item')
        if item:
            message = f'Session {session_id} retrieved successfully from DynamoDB.'
            logger.info(message)
            return item
        message = f'Session {session_id} not found in DynamoDB or has expired.'
        logger.info(message)
        return None
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code')
        error_msg = f'''DynamoDB ClientError retrieving session
                        {session_id}: {error_code} - {e}'''
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(
            detail = f'DynamoDB error retrieving session: {e}'
        ) from e
    except Exception as e:
        error_msg = f'''Unexpected error retrieving session
                        {session_id} from DynamoDB: {e}'''
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(
            detail = f'An unexpected error occurred while retrieving session: {e}'
        ) from e

async def delete_session_by_id(session_id: str) -> None:
    '''
        Deletes a form session record from DynamoDB by its session_id.
    '''
    table = dynamodb_client_instance.get_table()
    try:
        message = f'Attempting to delete session: {session_id}'
        logger.debug(message)
        response = table.delete_item(Key = {'session_id': session_id})
        message = f'Session {session_id} deleted successfully from DynamoDB.'
        logger.info(message)
        message = f'DynamoDB delete_item response: {response}'
        logger.debug(message)
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code')
        error_msg = f'''DynamoDB ClientError deleting session
                        {session_id}: {error_code} - {e}'''
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(
            detail = f'DynamoDB error deleting session: {e}'
        ) from e
    except Exception as e:
        error_msg = f'''Unexpected error deleting session
                        {session_id} from DynamoDB: {e}'''
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(
            detail = f'An unexpected error occurred while deleting session: {e}'
        ) from e
