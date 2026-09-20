'''
    What the ingest controllers share: the environment they read, the helpers
    that turn stored items back into DTOs, and the one way a companion load
    —payments, stock, visits— is stored and attached to its dataset.

    The three companions are the same operation over a different sheet: store
    the accepted rows as CSV, hang the key, the summary and the issues off the
    dataset item, answer with the summary. Stating it once here keeps the three
    from drifting apart, which is exactly what happened when the S3 upload path
    forgot two of them.
'''
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Optional, Type
from uuid import uuid4

from boto3.resources.base import ServiceResource
from pydantic import BaseModel

from schemas.ingest import IngestError
from services.environment import load_and_validate_env_vars
from services.exceptions import ResourceNotFoundError
from services.ingest_files import read_file, serialize_dataframe
from services.ingest_utils import attach_to_dataset, download_bytes, upload_bytes
from services.logger_config import custom_logger as logger

# Only a slice of the issues travels in the JSON response / DynamoDB item
# (400 KB limit); the full set lives in the rejected CSV in S3.
ENV_VARS = load_and_validate_env_vars({
    'MAX_ISSUES_ON_RESPONSE': int,
    'TEMPLATE_S3_KEY': str,
})
MAX_ISSUES_ON_RESPONSE = ENV_VARS['MAX_ISSUES_ON_RESPONSE']
# The MIME type of the rejected-rows download. It stays in the code because it
# describes the format of the file, not a decision anybody would take
# differently: a CSV is served as a CSV.
CSV_CONTENT_TYPE = 'text/csv'
# The template is a static object in the default bucket, not something the
# service builds: the format is fixed and the client is the one who complies
# with it. Changing it means changing business logic, so it moves over time and
# never at runtime.
TEMPLATE_S3_KEY = ENV_VARS['TEMPLATE_S3_KEY']


def native_numbers(stored: Dict[str, Any]) -> Dict[str, Any]:
    '''
        Turns the Decimals DynamoDB returns back into plain numbers.

        Args:
            stored (Dict[str, Any]): Attribute map as it came from the table.

        Returns:
            Dict[str, Any]: The same map, with numbers Pydantic accepts.
    '''
    return {
        key: float(value) if isinstance(value, Decimal) else value
        for key, value in stored.items()
    }


def load_sales_frame(dataset: Dict[str, Any]) -> Any:
    '''
        Reads the normalized sales rows of a dataset back from S3.

        A companion load has to be married against what was actually stored,
        not against the file the client happens to be holding: the stored frame
        is the one every other service reads.

        Args:
            dataset (Dict[str, Any]): The dataset item.

        Returns:
            pd.DataFrame: The normalized sales rows.

        Raises:
            ResourceNotFoundError: If the dataset has no stored file.
    '''
    file_key = dataset.get('file_s3_key')
    if not file_key:
        raise ResourceNotFoundError(detail = IngestError.DATASET_NOT_FOUND.value)
    return read_file(download_bytes(file_key), str(file_key))


@dataclass(frozen = True)
class CompanionSpec:
    '''
        How one companion contract is stored: the name that prefixes its S3
        folder and its dataset attributes, and the response it answers with.

        The response models are parallel on purpose —`<name>_s3_key`, summary,
        issues— so one storage routine serves the three.
    '''
    name: str
    response_model: Type[BaseModel]


async def store_companion(
    dynamodb_resource: ServiceResource,
    dataset: Dict[str, Any],
    result: Any,
    filename: str,
    spec: CompanionSpec
) -> BaseModel:
    '''
        Stores an accepted companion load and attaches it to its dataset.

        A new load REPLACES the previous one of the same kind: the dataset
        keeps one key per companion, so what the analysis reads is always the
        latest file and not an accumulation nobody can tell apart.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            dataset (Dict[str, Any]): Dataset the load belongs to.
            result (Any): Outcome of the companion pipeline: `accepted`,
                `issues` and `summary`.
            filename (str): Original filename, for the log.
            spec (CompanionSpec): Which companion this is.

        Returns:
            BaseModel: The companion's response: what got in, what did not,
                and why.
    '''
    dataset_id = str(dataset['dataset_id'])
    has_rows = len(result.accepted) > 0
    issues = result.issues[:MAX_ISSUES_ON_RESPONSE]

    stored_key: Optional[str] = None
    if has_rows:
        stored_key = upload_bytes(
            file_key = f'ingest/{spec.name}/{uuid4().hex}.csv',
            data = serialize_dataframe(result.accepted, f'{spec.name}.csv'),
            content_type = CSV_CONTENT_TYPE
        )
        attach_to_dataset(
            dynamodb_resource = dynamodb_resource,
            dataset_id = dataset_id,
            payload = {
                f'{spec.name}_s3_key': stored_key,
                f'{spec.name}_summary': result.summary.model_dump(),
                f'{spec.name}_issues': [issue.model_dump(mode = 'json') for issue in issues]
            }
        )

    message = (f'{spec.name.capitalize()} load for dataset {dataset_id} from "{filename}": '
               f'{result.summary.valid_rows} row(s), {len(result.issues)} issue(s).')
    logger.info(message)

    return spec.response_model(
        dataset_id = dataset_id,
        status = 'validated' if has_rows else 'failed',
        summary = result.summary,
        issues = issues,
        **{f'{spec.name}_s3_key': stored_key}
    )
