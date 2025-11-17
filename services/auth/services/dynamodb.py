'''
    Database connection service (DynamoDB)
'''
from typing import Dict, Any, Optional, List
import boto3
from botocore.exceptions import ClientError

from services.logger_config import custom_logger as logger
from services.exceptions import ServiceUnavailableError
from services.environment import load_and_validate_env_vars

dynamodb = boto3.resource('dynamodb')

ENV_VARS = load_and_validate_env_vars({'TABLE_NAME': str})
TABLE_NAME = ENV_VARS['TABLE_NAME']

def get_table():
    '''
        Returns a reference to the DynamoDB table.
    '''
    if not TABLE_NAME:
        error_msg = 'TABLE_NAME is not configured in environment or .env.'
        logger.critical(error_msg, exc_info = True)
        raise ServiceUnavailableError(
            detail = error_msg
        )

    try:
        table = dynamodb.Table(TABLE_NAME)
        message = f'DynamoDB table "{TABLE_NAME}" accessed successfully.'
        logger.info(message)
        return table
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code')
        error_msg = f'Error accessing DynamoDB table: {TABLE_NAME}: {error_code
                } {e.response.get('Error', {}).get('Message')}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(
            detail = f'Database initialization error: {error_msg}'
        ) from e
    except Exception as e:
        error_msg = f'Unexpected error when getting DynamoDB table {
            TABLE_NAME}: {e}'
        logger.critical(error_msg, exc_info = True)
        raise ServiceUnavailableError(
            detail = 'Unexpected database initialization error.'
        ) from e

def create_user_item(
    user_data: Dict[str, Any]
) -> Dict[str, Any]:
    '''
        Create a new user item in the DynamoDB table.
        user_data must contain 'email' (Partition Key), 'hashed_password', etc.
    '''
    table = get_table()
    user_email = user_data.get('email', 'N/A')
    try:
        table.put_item(
            Item = user_data,
            ConditionExpression = 'attribute_not_exists(email)'
        )
        message = f'User "{user_email}" created successfully in DynamoDB.'
        logger.info(message)
        return user_data
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            message = f'User with email "{user_email}" already exists.'
            logger.warning(message)
            raise ValueError(message) from e
        error_msg = f'Error creating user "{user_email}" in DynamoDB: {e}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(
            detail=f'Database write error: {e.response['Error']['Message']}'
        ) from e
    except Exception as e:
        log_msg = f'Unexpected error creating user \'{user_email}\' in DynamoDB: {e}'
        logger.critical(log_msg, exc_info = True)
        raise ServiceUnavailableError(
            detail='Unexpected database write error.'
        ) from e

def get_user_by_email(
    email: str
) -> Optional[Dict[str, Any]]:
    '''
        Gets a user from the DynamoDB table by their email (Partition Key).
    '''
    table = get_table()
    try:
        response = table.get_item(Key = {'email': email})
        user = response.get('Item')
        if user:
            message = f'User "{email}" retrieved successfully from DynamoDB.'
            logger.info(message)
        else:
            message = f'User "{email}" not found in DynamoDB.'
            logger.info(message)
        return user
    except ClientError as e:
        error_msg = f'Error getting user "{email}" from DynamoDB: {e}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(
            detail = 'Database read error.'
        ) from e
    except Exception as e:
        error_msg = f'Unexpected error getting user "{email}" from DynamoDB: {e}'
        logger.critical(error_msg, exc_info = True)
        raise ServiceUnavailableError(
            detail = 'Unexpected database read error.'
        ) from e

def update_user_item(
    email: str, update_expression: str,
    expression_attribute_values: Dict,
    expression_attribute_names: Optional[Dict] = None
) -> Optional[Dict[str, Any]]:
    '''
        Updates a user item in the DynamoDB table.
        email: The partition key of the user to update.
        update_expression: The update expression string (e.g., 'SET #fn = :fn, #ln = :ln').
        expression_attribute_values: Dictionary of values to update (e.g.,
        {':fn': 'New', ':ln': 'Last_Name'}).
        expression_attribute_names: Optional, for reserved attribute names
        (e.g., {'#fn': 'first_name'}).
    '''
    table = get_table()
    update_kwargs = {
        'Key': {'email': email},
        'UpdateExpression': update_expression,
        'ReturnValues': 'ALL_NEW'
    }
    if expression_attribute_values:
        update_kwargs['ExpressionAttributeValues'] = expression_attribute_values

    if expression_attribute_names:
        update_kwargs['ExpressionAttributeNames'] = expression_attribute_names

    try:
        response = table.update_item(**update_kwargs)
        updated_user = response.get('Attributes')
        if updated_user:
            message = f'User "{email}" updated successfully in DynamoDB.'
            logger.info(message)
        else:
            message = f'User "{email}" not found for update in DynamoDB.'
            logger.warning(message)
        return updated_user
    except ClientError as e:
        error_msg = f'Error updating user "{email}" in DynamoDB: {e}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(
            detail = 'Unexpected database update error.'
        ) from e

def delete_user_item(
    email: str
) -> bool:
    '''
        Deletes a user item from the DynamoDB table.
    '''
    table = get_table()
    try:
        response = table.delete_item(
            Key = {'email': email},
            ReturnValues = 'ALL_OLD'
        )
        if response.get('Attributes'):
            message = f'User "{email}" deleted successfully from DynamoDB.'
            logger.info(message)
            return True
        message = f'User "{email}" not found for deletion in DynamoDB.'
        logger.warning(message)
        return False
    except ClientError as e:
        error_msg = f'Error deleting user "{email}" from DynamoDB: {e}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(
            detail = f'Database delete error: {e.response['Error']['Message']}'
        ) from e
    except Exception as e:
        error_msg = f'Unexpected error deleting user "{email}" from DynamoDB: {e}'
        logger.critical(error_msg, exc_info = True)
        raise ServiceUnavailableError(
            detail = 'Unexpected database delete error.'
        ) from e

def scan_all_users() -> List[Dict[str, Any]]:
    '''
        Scans the entire user table.
        WARNING: Very inefficient for large tables. For administration/debugging purposes only.
    '''
    table = get_table()
    try:
        response = table.scan()
        users = response.get('Items', [])
        message = f'Scanned {len(users)} users from DynamoDB.'
        logger.info(message)
        while 'LastEvaluatedKey' in response:
            response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            users.extend(response.get('Items', []))
            message = f'Scanned additional {len(response.get('Items', []))
                } users. Total: {len(users)}'
            logger.info(message)
        return users
    except ClientError as e:
        error_msg = f'Error scanning all users from DynamoDB: {e}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(
            detail=f'Database scan error: {e.response['Error']['Message']}'
        ) from e
    except Exception as e:
        error_msg = f'Unexpected error scanning all users from DynamoDB: {e}'
        logger.critical(error_msg, exc_info = True)
        raise ServiceUnavailableError(
            detail='Unexpected database scan error.'
        ) from e
