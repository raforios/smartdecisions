'''
    DynamoDB Connection
'''
from typing import TypedDict, Callable
import boto3
from botocore.exceptions import ClientError as AWSClientError
from services.environment import load_and_validate_env_vars

class DynamoDBConfig(TypedDict):
    '''
    TypedDict to define the expected structure and types of DynamoDB parameters.
    '''
    AWS_REGION: str
    DYNAMODB_ENDPOINT_URL: str

_ENV_VARS = load_and_validate_env_vars(
    env_vars = {
        'AWS_REGION': str
    },
    optional_env_vars = {
        'DYNAMODB_ENDPOINT_URL': str
    }
)

def get_dynamodb_resource():
    '''
    Creates and returns a DynamoDB resource.
    
    Returns:
        boto3.resources.factory.ServiceResource: The DynamoDB resource.
    
    Raises:
        RuntimeError: If an unexpected error occurs during resource creation.
    '''
    try:
        if _ENV_VARS.get('DYNAMODB_ENDPOINT_URL'):
            # Conexión para entorno de desarrollo local (LocalStack o Docker)
            return boto3.resource(
                'dynamodb',
                region_name = _ENV_VARS['AWS_REGION'],
                endpoint_url = _ENV_VARS['DYNAMODB_ENDPOINT_URL']
            )
        # Conexión para entorno de producción en AWS
        return boto3.resource(
            'dynamodb',
            region_name = _ENV_VARS['AWS_REGION']
        )
    except AWSClientError as e:
        raise RuntimeError(f'Error de cliente de AWS al conectar a DynamoDB: {e}') from e
    except Exception as e:
        raise RuntimeError(f'Error inesperado al crear el recurso de DynamoDB: {e}') from e

# Instancia del recurso de DynamoDB para inyección de dependencia
DB_RESOURCE = get_dynamodb_resource()

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
        return DB_RESOURCE
    return _get_db

GET_DB_DEPENDENCY: Callable = get_db_resource()
