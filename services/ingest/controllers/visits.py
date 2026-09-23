'''
    Visits: what the sales force did on the street, the EXECUTED side of
    the routes that OPTIMIZATION compares against the plan.
'''
from boto3.resources.base import ServiceResource
from fastapi import Request

from controllers.common import CompanionSpec, load_sales_frame, store_companion
from schemas.ingest import VisitsResponse
from services.ingest_utils import get_owned_dataset
from services.visits import parse_and_validate
from services.utils import audit_event, handle_service_errors

# The controller signature is fixed by the route —resource, dataset, file,
# name, caller, request— and the three companion controllers are the same
# seven-line adapter over their own pipeline on purpose: what varies is the
# spec, and folding them into one would hide which process each route runs.
# pylint: disable=too-many-arguments, too-many-positional-arguments, duplicate-code

SPEC = CompanionSpec(name = 'visits', response_model = VisitsResponse)


@handle_service_errors('INGEST')
@audit_event('INGEST', 'Visits', 'UPLOAD')
async def ingest_visits_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    file_bytes: bytes,
    filename: str,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> VisitsResponse:
    '''
        Loads the visits of the sales force against an existing sales dataset.

            1. Read the dataset the caller owns, and its stored sales rows.
            2. Validate the visits and marry them to clients and sellers.
            3. Store the accepted rows and attach them to the dataset.

        Its own endpoint because the visits arrive after the sales: the file
        of the week is exported when the week is over. A new load REPLACES the
        previous one, so the executed side of the routes is always one file.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            dataset_id (str): Sales dataset the visits belongs to.
            file_bytes (bytes): Raw content of the uploaded file.
            filename (str): Original filename.
            current_user (str): Authenticated caller and owner of the dataset.

        Returns:
            VisitsResponse: Summary of the load and its issues.
    '''
    dataset = get_owned_dataset(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        owner_email = current_user
    )
    result = parse_and_validate(file_bytes, filename, load_sales_frame(dataset))
    return await store_companion(dynamodb_resource, dataset, result, filename, SPEC)
