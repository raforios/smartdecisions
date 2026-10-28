'''
    The shop's customers.

    Every invoice remembers its buyer. The write is one conditional update and
    not a read followed by a write: each field is set only `if_not_exists`, so
    two tills invoicing the same NIT at the same second cannot overwrite each
    other, and neither can overwrite a correction made from the customers
    screen.
'''
from typing import Any

from boto3.resources.base import ServiceResource

from models.billing import CUSTOMERS_TABLE, CUSTOMER_SORT_KEY, OWNER_KEY
from schemas.billing import BillingError, Buyer
from schemas.billing_customers import CustomerEdit, CustomerOut, CustomersResponse
from services.billing import from_dynamo, now_iso, read_partition, to_dynamo, write_item
from services.exceptions import RegisterNotFoundError
from services.logger_config import custom_logger as logger

# What a buyer carries that the customer keeps.
REMEMBERED_FIELDS = ('name', 'document_type', 'email')


def remember_customer(
    dynamodb_resource: ServiceResource,
    owner: str,
    buyer: Buyer,
    invoiced_by: str
) -> None:
    '''
        Creates the buyer as a customer, or fills what the customer lacked.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            buyer (Buyer): The buyer of an invoice, with its document.
            invoiced_by (str): Who issued the invoice.
    '''
    stamp = now_iso()
    values: dict[str, Any] = {':now': stamp, ':by': invoiced_by}
    names: dict[str, str] = {}
    clauses = ['created_at = if_not_exists(created_at, :now)',
               'created_by = if_not_exists(created_by, :by)',
               'last_invoiced_at = :now']
    for field in REMEMBERED_FIELDS:
        value = getattr(buyer, field)
        if value in (None, ''):
            continue
        # `name` is a reserved word in DynamoDB expressions.
        names[f'#{field}'] = field
        values[f':{field}'] = value
        clauses.append(f'#{field} = if_not_exists(#{field}, :{field})')

    request: dict[str, Any] = {
        'Key': {OWNER_KEY: owner, CUSTOMER_SORT_KEY: buyer.document.strip()},
        'UpdateExpression': 'SET ' + ', '.join(clauses),
        'ExpressionAttributeValues': to_dynamo(values)
    }
    if names:
        request['ExpressionAttributeNames'] = names
    dynamodb_resource.Table(CUSTOMERS_TABLE).update_item(**request)

    message = f'Customer {buyer.document} remembered for {owner}.'
    logger.info(message)


def get_customer(
    dynamodb_resource: ServiceResource,
    owner: str,
    document: str
) -> CustomerOut:
    '''
        One customer, by NIT or CI.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            document (str): The customer's document.

        Returns:
            CustomerOut: The customer.

        Raises:
            RegisterNotFoundError: The shop never invoiced that document.
    '''
    stored = from_dynamo(dynamodb_resource.Table(CUSTOMERS_TABLE).get_item(
        Key = {OWNER_KEY: owner, CUSTOMER_SORT_KEY: document.strip()}
    ).get('Item'))
    if not stored:
        raise RegisterNotFoundError(detail = BillingError.CUSTOMER_NOT_FOUND.value)
    return _customer_out(stored)


def list_customers(
    dynamodb_resource: ServiceResource,
    owner: str
) -> CustomersResponse:
    '''
        Every customer of the shop, by document.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.

        Returns:
            CustomersResponse: The customers.
    '''
    items = [_customer_out(row) for row in read_partition(dynamodb_resource,
                                                          CUSTOMERS_TABLE, owner)]
    return CustomersResponse(items = items, total = len(items))


def update_customer(
    dynamodb_resource: ServiceResource,
    owner: str,
    edit: CustomerEdit,
    updated_by: str
) -> CustomerOut:
    '''
        Corrects a customer: the explicit overwrite an invoice never does.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            edit (CustomerEdit): The document and the fields to replace.
            updated_by (str): Who corrects it.

        Returns:
            CustomerOut: The customer as it now stands.

        Raises:
            RegisterNotFoundError: The shop never invoiced that document.
    '''
    stored = get_customer(dynamodb_resource, owner, edit.document)
    changes = edit.model_dump(include = set(REMEMBERED_FIELDS), exclude_unset = True)
    corrected = stored.model_copy(update = {**changes, 'updated_at': now_iso(),
                                            'updated_by': updated_by})
    write_item(dynamodb_resource, CUSTOMERS_TABLE, {OWNER_KEY: owner, **corrected.model_dump()})

    message = f'Customer {edit.document} corrected by {updated_by} for {owner}.'
    logger.info(message)
    return corrected


def _customer_out(stored: dict[str, Any]) -> CustomerOut:
    '''
        A stored customer as the API returns it.

        Args:
            stored (dict[str, Any]): The item.

        Returns:
            CustomerOut: The customer.
    '''
    return CustomerOut(**{key: value for key, value in stored.items() if key != OWNER_KEY})
