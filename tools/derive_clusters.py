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

import pandas as pd

# First on purpose: importing it puts INGEST on the path and loads its .env.
# pylint: disable=wrong-import-order
from tools.ingest_env import BUCKET, DATASETS_TABLE, session
from schemas.clients import ClientSource, ClientUpsertSchema
from services.clients import list_clients, upsert_clients

# The bands, as cumulative share of revenue. The names are the account's to
# choose; these are the ones the prospect uses, so a demonstration against
# their workbook speaks their language.
BANDS = (
    (0.50, 'PLATINIUM'),
    (0.80, 'GOLD'),
    (1.01, 'SILVER')
)



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
    table = session().resource('dynamodb').Table(DATASETS_TABLE)
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


def _describe_bands(
    owner: str,
    sales: pd.DataFrame,
    clusters: pd.Series
) -> None:
    '''
        Prints how many clients fell in each band and what share of the sales
        they carry, so a bad cut is visible before anything is written.

        Args:
            owner (str): Owner key, for the heading.
            sales (pd.DataFrame): The normalized sales.
            clusters (pd.Series): Band of each client.

        Returns:
            None
    '''
    counts = clusters.value_counts()
    print(f'{owner}: {len(clusters)} clientes')
    for _, name in BANDS:
        if name in counts:
            billed = sales.loc[sales['pos_id'].map(clusters) == name, 'total_amount'].sum()
            print(f'  {name:10} {counts[name]:>4} clientes · '
                  f'{billed / sales["total_amount"].sum():.1%} de la venta')


def _update_master(
    owner: str,
    clusters: pd.Series
) -> None:
    '''
        Completes the cluster of each known client in the master.

        The master completes blanks and never overwrites, which is exactly what
        is wanted here: a cluster the company already declared stays.

        Args:
            owner (str): Owner key.
            clusters (pd.Series): Band of each client.

        Returns:
            None
    '''
    resource = session().resource('dynamodb')
    # `list_clients` hands back the stored items, which are TypedDicts.
    known = {str(item['id']): item for item in list_clients(resource, owner)}
    updates = [
        ClientUpsertSchema(id = str(code), name = known[str(code)].get('name') or str(code),
                           cluster = cluster)
        for code, cluster in clusters.items() if str(code) in known
    ]
    result = upsert_clients(resource, owner, updates, ClientSource.FILE)
    print(f'maestro: {result.completed} completado(s), {result.unchanged} sin cambio')


def main(argument_list: list | None = None) -> int:
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
    s3_client = session().client('s3')
    body = s3_client.get_object(Bucket = BUCKET, Key = key)['Body'].read()
    sales = pd.read_csv(io.BytesIO(body))

    clusters = clusters_from_volume(sales)
    _describe_bands(arguments.owner, sales, clusters)

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
    _update_master(arguments.owner, clusters)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
