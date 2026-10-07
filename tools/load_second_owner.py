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

    The other companions —collections, stock, visits— go through their own
    INGEST validators and attach to the dataset the same way the upload door
    attaches them.

    Usage:
        python -m tools.load_second_owner --owner "Sociedad de Cachivaches" \
            --sales /tmp/ventas.xlsx --objectives /tmp/objetivos.xlsx \
            --collections /tmp/cobros.xlsx --stock /tmp/stock.xlsx --visits /tmp/visitas.xlsx
        python -m tools.load_second_owner ... --yes    # escribe de verdad
'''
import argparse
import sys
from pathlib import Path
from uuid import uuid4

import boto3
from boto3.dynamodb.conditions import Attr
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
from services import collections, stock, visits  # noqa: E402
from services.ingest_utils import attach_to_dataset, persist_dataset  # noqa: E402
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
) -> str | None:
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


def main(argument_list: list | None = None) -> int:
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
    parser.add_argument('--collections', default = None, help = 'Collections file.')
    parser.add_argument('--stock', default = None, help = 'Stock file.')
    parser.add_argument('--visits', default = None, help = 'Visits file.')
    parser.add_argument('--replace', action = 'store_true',
                        help = 'Delete the owner\'s previous datasets, their runs and files.')
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

    for name, module, names_clients in (('collections', collections, False),
                                        ('stock', stock, False),
                                        ('visits', visits, True)):
        path = getattr(arguments, name)
        if path:
            _attach_companion((resource, arguments.owner, dataset_id, accepted),
                              name, (module, names_clients), Path(path), dry_run)

    if arguments.replace and not dry_run:
        datasets, runs = delete_previous_datasets(resource, arguments.owner, dataset_id)
        print(f'anteriores borrados: {datasets} dataset(s), {runs} análisis guardado(s)')

    if dry_run:
        print('\nSimulación: no se escribió nada. Repite con --yes.')
    return 0


def _scan_all(
    table,
    condition,
    keys_only: bool = False
) -> list:
    '''
        Every item of a table matching a condition, page after page: a run
        carries its results, so one page of `analytics_runs` is a handful.

        Args:
            table: A boto3 table.
            condition: A boto3 attribute condition.
            keys_only (bool): Bring only the key, not the stored results.

        Returns:
            list: The matching items.
    '''
    items: list = []
    arguments = {'FilterExpression': condition}
    if keys_only:
        arguments.update(ProjectionExpression = '#k', ExpressionAttributeNames = {'#k': 'id'})
    while True:
        page = table.scan(**arguments)
        items.extend(page['Items'])
        if 'LastEvaluatedKey' not in page:
            return items
        arguments['ExclusiveStartKey'] = page['LastEvaluatedKey']


def delete_previous_datasets(
    resource,
    owner: str,
    keep_id: str
) -> tuple:
    '''
        Deletes every dataset of the owner but the one just loaded: the item,
        the files it points to and the analysis runs computed over it. A demo
        company keeps one dataset, so the portal never opens a stale one.

        Args:
            resource: DynamoDB resource.
            owner (str): Owner key.
            keep_id (str): The dataset that stays.

        Returns:
            tuple: Datasets and runs deleted.
    '''
    datasets = [item for item in _scan_all(resource.Table('ingest_datasets'),
                                           Attr('owner_email').eq(owner))
                if item['id'] != keep_id]
    runs_deleted = 0
    for dataset in datasets:
        keys = {value for name, value in dataset.items()
                if name.endswith('s3_key') and isinstance(value, str)
                and value.startswith('ingest/')}
        runs = _scan_all(resource.Table('analytics_runs'),
                         Attr('dataset_id').eq(dataset['id']), keys_only = True)
        for key in keys:
            _s3().delete_object(Bucket = BUCKET, Key = key)
        with resource.Table('analytics_runs').batch_writer() as batch:
            for run in runs:
                batch.delete_item(Key = {'id': run['id']})
        resource.Table('ingest_datasets').delete_item(Key = {'id': dataset['id']})
        runs_deleted += len(runs)
    return len(datasets), runs_deleted


def _attach_companion(
    target: tuple,
    name: str,
    pipeline: tuple,
    path: Path,
    dry_run: bool
) -> None:
    '''
        Validates a companion file with INGEST's own pipeline and attaches it
        to the dataset, as the upload door does.

        Args:
            target (tuple): DynamoDB resource, owner, dataset id and the
                accepted sales the companion is checked against.
            name (str): Companion name: collections, stock or visits.
            pipeline (tuple): The INGEST module and whether it names clients.
            path (Path): The file.
            dry_run (bool): True to report without writing.
    '''
    resource, owner, dataset_id, sales = target
    module, names_clients = pipeline
    result = module.parse_and_validate(path.read_bytes(), path.name, sales)
    accepted = result.accepted
    if names_clients and len(accepted) > 0 and not dry_run:
        accepted = sync_master(
            dynamodb_resource = resource, owner_email = owner, frame = accepted,
            columns = CLIENT_FRAME_COLUMNS, source = ClientSource.FILE
        )
    print(f'{name}: {result.summary.valid_rows} válidas, {len(result.issues)} observaciones')
    key = _store(accepted, name, dry_run)
    print(f'{name} -> {key}')
    if not dry_run:
        attach_to_dataset(dynamodb_resource = resource, dataset_id = dataset_id, payload = {
            f'{name}_s3_key': key,
            f'{name}_summary': to_dynamo(result.summary.model_dump(mode = 'json')),
            f'{name}_issues': [issue.model_dump(mode = 'json') for issue in result.issues[:50]]
        })


if __name__ == '__main__':
    raise SystemExit(main())
