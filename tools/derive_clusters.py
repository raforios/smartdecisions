'''
    Derives a commercial cluster for each client from what they actually buy.

    The cluster is normally a DECISION: the company says which clients are
    platinum. But an account that has never declared one leaves the whole
    cluster-by-semaphore matrix grouped under a single «unassigned» cell, which
    is the one view that makes the attainment report worth reading.

    So this proposes an initial tiering from the client's own volume, the way
    the prospect's own workbook derives it — their `CLUSTER 2020` comes out of
    `FACT 2019`. The bands are cumulative share of revenue, which is how a
    commercial team actually thinks about it: the handful of clients that carry
    half the business are not the same kind of client as the long tail.

    It writes the cluster in TWO places, and both matter:
      * the client master, because that is where what describes a client lives;
      * the stored sales frame, because that is what the analysis reads.

    It is a proposal, not a verdict. The moment the company declares its own
    clusters, a client upload overwrites these — the master never reverses a
    correction.

    Usage:
        python -m tools.derive_clusters --owner "Distribuidora Andina S.R.L."
        python -m tools.derive_clusters --owner "..." --yes
'''
import argparse
import io
import sys
from pathlib import Path
from typing import Optional

import boto3
import pandas as pd
from dotenv import load_dotenv

INGEST_PATH = Path(__file__).resolve().parent.parent / 'services' / 'ingest'
sys.path.insert(0, str(INGEST_PATH))
load_dotenv(INGEST_PATH / '.env')

# pylint: disable=wrong-import-position
from services.clients import list_clients, upsert_clients  # noqa: E402
from schemas.clients import ClientSource, ClientUpsertSchema  # noqa: E402

BUCKET = 'ml-data-file-handler'
PROFILE = 'deploy_ml'
REGION = 'us-east-1'
DATASETS_TABLE = 'ingest_datasets'

# The bands, as cumulative share of revenue. The names are the account's to
# choose; these are the ones the prospect uses, so a demonstration against
# their workbook speaks their language.
BANDS = (
    (0.50, 'PLATINIUM'),
    (0.80, 'GOLD'),
    (1.01, 'SILVER')
)


def _session():
    '''
        The AWS session of the deployment profile.

        Returns:
            boto3.Session: The session.
    '''
    return boto3.Session(profile_name = PROFILE, region_name = REGION)


def _dataset_of(owner: str) -> dict:
    '''
        The owner's dataset record.

        Args:
            owner (str): Owner key.

        Returns:
            dict: The dataset item.

        Raises:
            SystemExit: The owner has no dataset.
    '''
    table = _session().resource('dynamodb').Table(DATASETS_TABLE)
    found = [item for item in table.scan().get('Items', [])
             if item.get('owner_email') == owner]
    if not found:
        raise SystemExit(f'No hay dataset de {owner!r}.')
    return found[0]


def clusters_from_volume(sales: pd.DataFrame) -> pd.Series:
    '''
        The cluster of each client, from their share of the revenue.

        Args:
            sales (pd.DataFrame): Normalized sales rows.

        Returns:
            pd.Series: Cluster per client, indexed by `pos_id`.
    '''
    volume = sales.groupby('pos_id')['total_amount'].sum().sort_values(ascending = False)
    share = volume.cumsum() / volume.sum()
    return share.map(
        lambda reached: next(name for limit, name in BANDS if reached <= limit)
    )


def main(argument_list: Optional[list] = None) -> int:
    '''
        Entry point.

        Args:
            argument_list (list): Arguments, for tests. Defaults to argv.

        Returns:
            int: Process exit code.
    '''
    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument('--owner', required = True, help = 'Owner key of the account.')
    parser.add_argument('--yes', action = 'store_true', help = 'Write for real.')
    arguments = parser.parse_args(argument_list)
    dry_run = not arguments.yes

    dataset = _dataset_of(arguments.owner)
    key = str(dataset['file_s3_key'])
    s3_client = _session().client('s3')
    body = s3_client.get_object(Bucket = BUCKET, Key = key)['Body'].read()
    sales = pd.read_csv(io.BytesIO(body))

    clusters = clusters_from_volume(sales)
    counts = clusters.value_counts()
    print(f'{arguments.owner}: {len(clusters)} clientes')
    for _, name in BANDS:
        if name in counts:
            billed = sales.loc[
                sales['pos_id'].map(clusters) == name, 'total_amount'
            ].sum()
            print(f'  {name:10} {counts[name]:>4} clientes · '
                  f'{billed / sales["total_amount"].sum():.1%} de la venta')

    sales['cluster'] = sales['pos_id'].map(clusters)
    if dry_run:
        print(f'\nSe reescribiría {key} y {len(clusters)} filas del maestro.')
        print('Simulación: no se escribió nada. Repite con --yes.')
        return 0

    # Same key: the dataset keeps pointing at its file, so nothing else moves.
    buffer = io.StringIO()
    sales.to_csv(buffer, index = False)
    s3_client.put_object(Bucket = BUCKET, Key = key,
                         Body = buffer.getvalue().encode('utf-8'),
                         ContentType = 'text/csv')
    print(f'\nreescrito {key}')

    resource = _session().resource('dynamodb')
    # `list_clients` hands back the stored items, which are TypedDicts.
    known = {str(item['id']): item for item in list_clients(resource, arguments.owner)}
    updates = [
        ClientUpsertSchema(id = str(code), name = known[str(code)].get('name') or str(code),
                           cluster = cluster)
        for code, cluster in clusters.items() if str(code) in known
    ]
    # The master completes blanks and never overwrites, which is exactly what
    # is wanted here: a cluster the company already declared stays.
    result = upsert_clients(resource, arguments.owner, updates, ClientSource.FILE)
    print(f'maestro: {result.completed} completado(s), {result.unchanged} sin cambio')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
