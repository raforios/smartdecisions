'''
    Exceptions service
'''
from typing import Optional, Dict, Any
from fastapi import HTTPException, status

class RegisterNotFoundError(HTTPException):
    '''
        Exception raised when a requested register is not found in the database.
        Returns HTTP 404 Not Found.
    '''
    def __init__(self, detail: str = 'Register not found',
                headers: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = detail,
            headers = headers
        )

class ResourceNotFoundError(HTTPException):
    '''
        Exception raised when a requested resource (e.g., file, bucket) is not found.
        Returns HTTP 404 Not Found.
    '''
    def __init__(self, detail: str = 'Resource not found',
                headers: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = detail,
            headers = headers
        )

class RegisterAlreadyExistsError(HTTPException):
    '''
        Exception raised when an attempt is made to create a register with a
        unique identifier (e.g., code) that already exists.
        Returns HTTP 409 Conflict.
    '''
    def __init__(self, detail: str = 'A register with this code already exists',
                headers: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code = status.HTTP_409_CONFLICT,
            detail = detail,
            headers = headers
        )

class InvalidInputError(HTTPException):
    '''
        Exception raised for invalid input data that doesn't fit a Pydantic
        validation error, but is a business logic validation failure.
        Returns HTTP 400 Bad Request.
    '''
    def __init__(self, detail: str = 'Invalid input data',
                headers: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code = status.HTTP_400_BAD_REQUEST,
            detail = detail,
            headers = headers
        )

class UnauthorizedError(HTTPException):
    '''
        Exception thrown when a user attempts to access a protected resource without
        valid or required authentication credentials.
        Returns HTTP 401 Unauthorized.
        This means that authentication is required and has failed or has not been provided.
    '''
    def __init__(self, detail: str = 'Unauthorized',
                headers: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = detail,
            headers = headers
        )

class ForbiddenError(HTTPException):
    '''
        Exception thrown when a user is authenticated but does not have
        permission to access a specific resource or perform an action.
        Returns HTTP 403 Forbidden.
        This means the server refuses to authorize the request.
    '''
    def __init__(self, detail: str = 'Access Forbidden',
                headers: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code = status.HTTP_403_FORBIDDEN,
            detail = detail,
            headers = headers
        )

class ServiceUnavailableError(HTTPException):
    '''
        Exception raised when an external service required for an operation is unavailable or fails.
        Returns HTTP 503 Service Unavailable.
    '''
    def __init__(self, detail: str = 'Service is currently unavailable. Please try again later.',
                headers: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE,
            detail = detail,
            headers = headers
        )
