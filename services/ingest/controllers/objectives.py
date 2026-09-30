'''
    Objectives: what the company decided each client should buy in a month,
    loaded against an existing sales dataset and measured against it.
'''
from boto3.resources.base import ServiceResource
from fastapi import Request

from controllers.common import CompanionSpec, load_sales_frame, store_companion
from schemas.ingest import ObjectivesResponse
from services.ingest_utils import get_owned_dataset
from services.objectives import parse_and_validate
from services.utils import audit_event, handle_service_errors

# The controller signature is fixed by the route —resource, dataset, file,
# name, caller, request— and the companion controllers are the same short
# adapter over their own pipeline on purpose: what varies is the spec.
# pylint: disable=too-many-arguments, too-many-positional-arguments, duplicate-code

# A client has ONE objective per month. Sending March again corrects March
# instead of leaving two objectives for it — they get revised mid-quarter,
# and a second truth for one month makes every percentage below it
# meaningless.
#
# It names clients and therefore feeds the master: a company sets objectives
# for the client it intends to activate, who by definition has no invoice yet.
SPEC = CompanionSpec(
    name = 'objectives',
    response_model = ObjectivesResponse,
    merge_keys = ('pos_id', 'period'),
    names_clients = True
)


@handle_service_errors('INGEST')
@audit_event('INGEST', 'Objectives', 'UPLOAD')
async def ingest_objectives_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    file_bytes: bytes,
    filename: str,
    current_user: str,
    auth_token: str,
    request: Request # pylint: disable=unused-argument
) -> ObjectivesResponse:
    '''
        Loads an objectives file against an existing sales dataset.

            1. Read the dataset the caller owns, and its stored sales rows.
            2. Validate the objectives and match them to the clients billed.
            3. Store the accepted rows and attach them to the dataset.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            dataset_id (str): Sales dataset the objectives belong to.
            file_bytes (bytes): Raw content of the uploaded file.
            filename (str): Original filename.
            current_user (str): Authenticated caller and owner of the dataset.
            auth_token (str): The caller's Authorization header, forwarded to FILES.

        Returns:
            ObjectivesResponse: Summary of the load and its issues.
    '''
    dataset = get_owned_dataset(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        owner_email = current_user
    )
    result = parse_and_validate(file_bytes, filename, load_sales_frame(dataset, auth_token))
    return await store_companion(dynamodb_resource, dataset, result, SPEC,
                                 (filename, auth_token))
