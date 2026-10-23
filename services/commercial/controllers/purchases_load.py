'''
    Purchases: what came into the warehouse and at what cost, married to the
    product catalogue of the sales dataset.
'''
from boto3.resources.base import ServiceResource
from fastapi import Request

from controllers.common import (
    CompanionSpec,
    LoadContext,
    load_sales_frame,
    merge_if_appending,
    store_companion
)
from schemas.channels import LoadMode
from schemas.commercial import PurchasesResponse
from services.commercial_utils import get_owned_dataset
from services.purchases_load import parse_and_validate, validate_rows
from services.utils import audit_event, handle_service_errors

# The controller signature is fixed by the route —resource, dataset, file,
# name, caller, request—, the same adapter as the other companions.
# pylint: disable=too-many-arguments, too-many-positional-arguments, duplicate-code

# A purchase is a ledger row: the same product bought from the same supplier
# on the same day at the same cost and quantity is the same row, so an ERP
# retry does not double it. Every load adds to the stored ones: the point of
# purchases is comparing the last one with the previous ones.
SPEC = CompanionSpec(
    name = 'purchases',
    response_model = PurchasesResponse,
    merge_keys = ('purchase_date', 'supplier', 'product_id', 'quantity', 'unit_cost',
                  'currency'),
    keeps_history = True
)


@handle_service_errors('COMMERCIAL')
@audit_event('COMMERCIAL', 'Purchases', 'UPLOAD')
async def ingest_purchases_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    file_bytes: bytes,
    filename: str,
    current_user: str,
    auth_token: str,
    request: Request # pylint: disable=unused-argument
) -> PurchasesResponse:
    '''
        Loads a purchases file against an existing sales dataset, on top of
        the purchases already stored.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            dataset_id (str): Sales dataset the purchases belong to.
            file_bytes (bytes): Raw content of the uploaded file.
            filename (str): Original filename.
            current_user (str): Authenticated caller and owner of the dataset.
            auth_token (str): The caller's Authorization header, forwarded to FILES.

        Returns:
            PurchasesResponse: Summary of the load and its issues.
    '''
    dataset = get_owned_dataset(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        owner_email = current_user
    )
    sales = load_sales_frame(dataset, auth_token)
    result = merge_if_appending(
        LoadContext(dataset, SPEC, LoadMode.REPLACE, sales, validate_rows, filename, auth_token),
        parse_and_validate(file_bytes, filename, sales)
    )
    return await store_companion(dynamodb_resource, dataset, result, SPEC,
                                 (filename, auth_token))
