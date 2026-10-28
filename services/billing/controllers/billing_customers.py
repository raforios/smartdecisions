'''
    The shop's customers: orchestration between the HTTP layer and the
    services.

    Same contract as `controllers/billing.py`: every controller carries
    `@handle_service_errors`, and the one that corrects a customer carries
    `@audit_event`.
'''
from boto3.resources.base import ServiceResource
from fastapi import Request

from schemas.billing_customers import CustomerEdit, CustomerOut, CustomersResponse
from services import billing_customers
from services.utils import audit_event, handle_service_errors

SERVICE = 'BILLING'


@handle_service_errors(SERVICE)
async def list_customers_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> CustomersResponse:
    '''
        Every customer of the shop.
    '''
    return billing_customers.list_customers(dynamodb_resource, owner)


@handle_service_errors(SERVICE)
async def get_customer_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    document: str,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> CustomerOut:
    '''
        One customer, by NIT or CI.
    '''
    return billing_customers.get_customer(dynamodb_resource, owner, document)


@handle_service_errors(SERVICE)
@audit_event(SERVICE, 'Customer', 'UPDATE', id_field = 'document')
async def update_customer_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    edit: CustomerEdit,
    request: Request, # pylint: disable=unused-argument
    current_user: str
) -> CustomerOut:
    '''
        Corrects a customer.
    '''
    return billing_customers.update_customer(dynamodb_resource, owner, edit, current_user)
