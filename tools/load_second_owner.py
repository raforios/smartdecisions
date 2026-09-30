'''
    Loads a second data owner, to show that isolation is real.

    A demonstration where all the data belongs to one account proves nothing
    about isolation: the query that forgot its owner filter looks identical to
    the one that did not. This loads a whole second company —its own sales, its
    own clients, its own objectives— so that logging in as one and seeing none
    of the other's figures is an observable fact.

    It runs INGEST's own pipeline rather than reimplementing it: the same
    validator, the same client master, the same normalisation. What it skips is
    only the HTTP layer, which is what lets it run with our AWS credentials
    instead of impersonating a user — nothing here forges a token.

    The owner key is NOT the e-mail. Since the JWT carries `client`, the owner
    of this account's data is that client name, and using the e-mail instead
    would file the rows where the account will never look for them.

    Usage:
        python -m tools.load_second_owner --owner "Sociedad de Cachivaches" \
            --sales /tmp/ventas.xlsx --objectives /tmp/objetivos.xlsx
        python -m tools.load_second_owner ... --yes    # escribe de verdad
'''
import argparse
import sys
from pathlib import Path
from typing import Optional
from uuid import uuid4

import boto3
from dotenv import load_dotenv

INGEST_PATH = Path(__file__).resolve().parent.parent / 'services' / 'ingest'
sys.path.insert(0, str(INGEST_PATH))

# The service reads its configuration from its own directory, so it has to be
# loaded before importing anything of it: its modules validate the environment
# at import time, which is what makes a missing variable fail at startup
# instead of halfway through a load.
load_dotenv(INGEST_PATH / '.env')

# pylint: disable=wrong-import-position
from schemas.clients import ClientSource  # noqa: E402
from services.clients import CLIENT_FRAME_COLUMNS, sync_master  # noqa: E402
from services.ingest import parse_and_validate_partial  # noqa: E402
from services.ingest_files import serialize_dataframe  # noqa: E402
from services.ingest_utils import persist_dataset  # noqa: E402
from services.ingest_utils import to_dynamo  # noqa: E402
from services.objectives import parse_and_validate as parse_objectives  # noqa: E402

BUCKET = 'ml-data-file-handler'
PROFILE = 'deploy_ml'
REGION = 'us-east-1'
CSV_TYPE = 'text/csv'


def _s3():
    '''
        The S3 client of the deployment profile.

        Direct and not through FILES on purpose: this is a maintenance task run
        with our own credentials, not a request on behalf of a user, and there
        is no token to forward.

        Returns:
            The boto3 S3 client.
    '''
    return boto3.Session(profile_name = PROFILE, region_name = REGION).client('s3')


def _dynamodb():
    '''
        The DynamoDB resource of the deployment profile.

        Returns:
            The boto3 DynamoDB resource.
    '''
    return boto3.Session(profile_name = PROFILE, region_name = REGION).resource('dynamodb')


def _store(
    frame,
    folder: str,
    dry_run: bool
) -> Optional[str]:
    '''
        Writes one frame where the service expects to find it.

        Args:
            frame: Rows to store.
            folder (str): Folder under the ingest prefix.
            dry_run (bool): True to report without writing.

        Returns:
            str | None: The object key.
    '''
    if frame.empty:
        return None
    key = f'ingest/{folder}/{uuid4().hex}.csv'
    if dry_run:
        return f'{key} (simulado)'
    _s3().put_object(
        Bucket = BUCKET, Key = key,
        Body = serialize_dataframe(frame, f'{folder}.csv'),
        ContentType = CSV_TYPE
    )
    return key


def main(argument_list: Optional[list] = None) -> int:
    '''
        Entry point.

        Args:
            argument_list (list): Arguments, for tests. Defaults to argv.

        Returns:
            int: Process exit code.
    '''
    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument('--owner', required = True,
                        help = 'Owner key: the JWT client, not the e-mail.')
    parser.add_argument('--sales', required = True, help = 'Sales file, template-shaped.')
    parser.add_argument('--objectives', default = None, help = 'Objectives file.')
    parser.add_argument('--yes', action = 'store_true', help = 'Write for real.')
    arguments = parser.parse_args(argument_list)
    dry_run = not arguments.yes

    sales_bytes = Path(arguments.sales).read_bytes()
    result = parse_and_validate_partial(sales_bytes, Path(arguments.sales).name)
    print(f'ventas: {result.summary.valid_rows} válidas de {result.summary.total_rows}, '
          f'{result.summary.error_rows} apartadas')

    resource = _dynamodb()
    accepted = result.accepted
    if not dry_run:
        # The master learns who the clients are and hands the frame back with
        # what it already knew filled in — exactly as the upload door does.
        accepted = sync_master(
            dynamodb_resource = resource, owner_email = arguments.owner,
            frame = accepted, columns = CLIENT_FRAME_COLUMNS,
            source = ClientSource.FILE
        )
    print(f'clientes en el maestro: {accepted["pos_id"].nunique()}')

    normalized_key = _store(accepted, 'normalized', dry_run)
    rejected_key = _store(result.rejected, 'rejected', dry_run)
    print(f'normalizado -> {normalized_key}')

    payload = {
        'owner_email': arguments.owner,
        'status': 'validated',
        'file_s3_key': normalized_key,
        'rejected_s3_key': rejected_key,
        'file_name': Path(arguments.sales).name,
        **result.summary.model_dump()
    }
    if dry_run:
        print(f'dataset -> simulado para dueño "{arguments.owner}"')
        dataset_id = 'simulado'
    else:
        dataset = persist_dataset(dynamodb_resource = resource, payload = payload)
        dataset_id = dataset['dataset_id']
        print(f'dataset -> {dataset_id} (dueño "{arguments.owner}")')

    if arguments.objectives:
        objectives = parse_objectives(
            Path(arguments.objectives).read_bytes(),
            Path(arguments.objectives).name,
            accepted
        )
        print(f'objetivos: {objectives.summary.valid_rows} válidos sobre '
              f'{objectives.summary.periods_count} mes(es), '
              f'{objectives.summary.unmatched_rows} sin venta')
        key = _store(objectives.accepted, 'objectives', dry_run)
        print(f'objetivos -> {key}')
        if not dry_run:
            resource.Table('ingest_datasets').update_item(
                Key = {'id': dataset_id},
                UpdateExpression = 'SET objectives_s3_key = :k, objectives_summary = :s',
                # Through `to_dynamo`: DynamoDB refuses floats, and the
                # summary carries amounts. The service converts with this same
                # function, so the item looks identical whichever door wrote it.
                ExpressionAttributeValues = {
                    ':k': key,
                    ':s': to_dynamo(objectives.summary.model_dump(mode = 'json'))
                }
            )
            print('objetivos enganchados al dataset')

    if dry_run:
        print('\nSimulación: no se escribió nada. Repite con --yes.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
