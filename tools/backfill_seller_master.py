'''
    Fills the seller master from the datasets loaded before it existed.

    Every load since the master was added registers its sellers on its own,
    through `sync_master`. The datasets already in production came in before
    that, and re-uploading them would not help: a file is recognised by its
    content and the same file is the same dataset, so it never goes through the
    sync again. This reads each stored sales file once and registers the
    sellers it names, with INGEST's own function — created when missing, never
    rewritten.

    Direct S3 and DynamoDB on purpose: a maintenance task run with our own
    credentials, not a request on behalf of a user, so there is no token to
    forward to FILES.

    Usage:
        python -m tools.backfill_seller_master          # informa qué crearía
        python -m tools.backfill_seller_master --yes    # escribe de verdad
'''
import argparse
import io
import sys
from typing import Any

import pandas as pd
from botocore.config import Config

# First on purpose: importing it puts INGEST on the path and loads its .env.
# pylint: disable=wrong-import-order
from tools.ingest_env import BUCKET, DATASETS_TABLE, session
from schemas.clients import ClientSource
from services.sellers import list_sellers, register_sellers, sellers_from_frame
# A normalized sales file is several MB; on a shared or slow link the default
# 60 s read timeout cut the download. Patience and retries, not a failure.
S3_CONFIG = Config(read_timeout = 300, connect_timeout = 30, retries = {'max_attempts': 5})



def _sales_frame(
    s3_client: Any,
    key: str
) -> pd.DataFrame:
    '''
        One stored, normalized sales file.

        Args:
            s3_client: The boto3 S3 client.
            key (str): Object key of the normalized CSV.

        Returns:
            pd.DataFrame: Its rows, read as text.
    '''
    body = s3_client.get_object(Bucket = BUCKET, Key = key)['Body'].read()
    return pd.read_csv(io.BytesIO(body), dtype = str)


def main(argument_list: list | None = None) -> int:
    '''
        Registers the sellers of every validated dataset.

        Args:
            argument_list (list | None): CLI arguments, for tests.

        Returns:
            int: Process exit code.
    '''
    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument('--yes', action = 'store_true', help = 'Write for real.')
    arguments = parser.parse_args(argument_list)

    aws = session()
    dynamodb = aws.resource('dynamodb')
    s3_client = aws.client('s3', config = S3_CONFIG)
    datasets = dynamodb.Table(DATASETS_TABLE).scan().get('Items', [])

    for dataset in datasets:
        owner = dataset.get('owner_email')
        key = dataset.get('file_s3_key')
        if dataset.get('status') != 'validated' or not owner or not key:
            continue
        sellers = sellers_from_frame(_sales_frame(s3_client, str(key)))
        known = {item['id'] for item in list_sellers(dynamodb, owner)}
        missing = [seller for seller in sellers if seller not in known]
        print(f'{owner}: {len(sellers)} vendedor(es) en el archivo, '
              f'{len(missing)} por crear: {", ".join(missing) or "—"}')
        if arguments.yes and missing:
            register_sellers(dynamodb, owner, missing, ClientSource.FILE)

    if not arguments.yes:
        print('\nSimulación: no se escribió nada. Repite con --yes.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
