'''
    The shop's customers: HTTP layer.

    Anybody of the shop reads them, which is what the counter needs to fill a
    known buyer; only whoever runs the shop corrects one. The owner is the shop
    the token names, never a parameter.
'''
from boto3.resources.base import ServiceResource
from fastapi import APIRouter, Body, Depends, Path, Request

from controllers.billing_customers import (
    get_customer_controller,
    list_customers_controller,
    update_customer_controller
)
from schemas.billing_customers import CustomerEdit, CustomerOut, CustomerPatch, CustomersResponse
from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger
from services.security import get_current_owner, get_current_user, require_roles

router = APIRouter(prefix = '/v1/billing/customers', tags = ['Billing — Customers'])

# Same pair that runs the shop in `routes/billing.py`.
MANAGERS = ('ADMIN', 'MANAGER')


def customer_edit(
    patch: CustomerPatch = Body(...),
    document: str = Path(..., min_length = 1, max_length = 40)
) -> CustomerEdit:
    '''
        Which customer is corrected and how.

        Args:
            patch (CustomerPatch): The fields to replace.
            document (str): The customer's NIT or CI.

        Returns:
            CustomerEdit: The edit the controller receives.
    '''
    return CustomerEdit(document = document, **patch.model_dump(exclude_unset = True))


@router.get('', response_model = CustomersResponse)
async def list_customers_endpoint(
    request: Request,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(get_current_owner),
    current_user: str = Depends(get_current_user)
) -> CustomersResponse:
    ''' Endpoint for every customer of the shop. '''
    return await list_customers_controller(
        dynamodb_resource = dynamodb_resource, owner = owner,
        request = request, current_user = current_user
    )


@router.get('/{document}', response_model = CustomerOut)
async def get_customer_endpoint(
    request: Request,
    document: str = Path(..., min_length = 1, max_length = 40),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(get_current_owner),
    current_user: str = Depends(get_current_user)
) -> CustomerOut:
    ''' Endpoint for one customer, by NIT or CI. '''
    return await get_customer_controller(
        dynamodb_resource = dynamodb_resource, owner = owner, document = document,
        request = request, current_user = current_user
    )


@router.patch('/{document}', response_model = CustomerOut)
async def update_customer_endpoint(
    request: Request,
    edit: CustomerEdit = Depends(customer_edit),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(require_roles(*MANAGERS)),
    current_user: str = Depends(get_current_user)
) -> CustomerOut:
    ''' Endpoint to correct a customer. '''
    message = f'Shop {owner}: {current_user} corrects customer {edit.document}.'
    logger.info(message)
    return await update_customer_controller(
        dynamodb_resource = dynamodb_resource, owner = owner, edit = edit,
        request = request, current_user = current_user
    )
