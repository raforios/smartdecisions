'''
    The INGEST service, on the path and configured, for the tools that reuse
    its functions instead of copying them.

    Importing this module is the setup: the service validates its environment
    at import time, so its `.env` has to be loaded before anything of it is
    imported, and its folder has to be on the path for `services.*` and
    `schemas.*` to resolve. Every tool that works on INGEST data imports this
    first.

        from tools.ingest_env import BUCKET, session
        from services.clients import list_clients
'''
import sys
from pathlib import Path

import boto3
from dotenv import load_dotenv

INGEST_PATH = Path(__file__).resolve().parent.parent / 'services' / 'ingest'
sys.path.insert(0, str(INGEST_PATH))
load_dotenv(INGEST_PATH / '.env')

BUCKET = 'ml-data-file-handler'
PROFILE = 'deploy_ml'
REGION = 'us-east-1'
DATASETS_TABLE = 'ingest_datasets'


def session() -> boto3.Session:
    '''
        The AWS session of the deployment profile.

        Returns:
            boto3.Session: Session bound to the profile and region.
    '''
    return boto3.Session(profile_name = PROFILE, region_name = REGION)
