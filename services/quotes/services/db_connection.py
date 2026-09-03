'''
    DynamoDB Connection
'''
from typing import Callable
import boto3
from botocore.exceptions import ClientError
from services.logger_config import custom_logger as logger
from services.exceptions import ServiceUnavailableError

# Inicializa la conexión de boto3
dynamodb_resource = boto3.resource('dynamodb')

def get_db_resource() -> Callable:
    '''
        Returns a callable that provides the DynamoDB resource.
        
        Returns:
            Callable: A callable to obtain a DynamoDB resource.
    '''
    def _get_db():
        '''
        Provides the DynamoDB resource as a dependency.
        '''
        return dynamodb_resource
    return _get_db

def get_table(table_name: str):
    '''
        Returns a reference to the specified DynamoDB table.
    '''
    try:
        table = dynamodb_resource.Table(table_name)
        message = f'DynamoDB table "{table_name}" accessed successfully.'
        logger.info(message)
        return table
    except ClientError as e:
        error_msg = f'Error accessing DynamoDB table "{table_name}": {
            e.response.get("Error", {}).get("Message")}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(
            detail = f'Database initialization error: {error_msg}'
        ) from e
    except Exception as e:
        error_msg = f'Unexpected error when getting DynamoDB table {table_name}: {e}'
        logger.critical(error_msg, exc_info = True)
        raise ServiceUnavailableError(
            detail = 'Unexpected database initialization error.'
        ) from e

# Instancia de la dependencia para su uso en FastAPI
GET_DB_DEPENDENCY: Callable = get_db_resource() # pylint: disable=invalid-name
