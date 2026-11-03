'''
    Shared DynamoDB (moto) helpers for the quotation tests.

    The two quotation tables are provisioned the way the deploy does, and the
    official catalogue is seeded with the ids 1..n in OFFICIAL_MINERALS order,
    so every test only declares the prices it needs.
'''
import boto3
from boto3.resources.base import ServiceResource

from models.mining_analysis import MineralItem
from services import prices_dyb
from services.mining_analysis import OFFICIAL_MINERALS, normalize_name


def build_quotation_tables() -> ServiceResource:
    '''
        Creates a mocked DynamoDB resource with the minerals and prices tables.

        Must be called inside an active ``moto.mock_aws()`` context.

        Returns:
            ServiceResource: The boto3 DynamoDB resource with both tables.
    '''
    resource = boto3.resource('dynamodb', region_name = 'us-east-1')
    resource.create_table(
        TableName = prices_dyb.MINERALS_TABLE,
        KeySchema = [{'AttributeName': 'mineral_id', 'KeyType': 'HASH'}],
        AttributeDefinitions = [{'AttributeName': 'mineral_id', 'AttributeType': 'S'}],
        BillingMode = 'PAY_PER_REQUEST'
    )
    resource.create_table(
        TableName = prices_dyb.PRICES_TABLE,
        KeySchema = [
            {'AttributeName': 'mineral_id', 'KeyType': 'HASH'},
            {'AttributeName': 'date', 'KeyType': 'RANGE'}
        ],
        AttributeDefinitions = [
            {'AttributeName': 'mineral_id', 'AttributeType': 'S'},
            {'AttributeName': 'date', 'AttributeType': 'S'}
        ],
        BillingMode = 'PAY_PER_REQUEST'
    )
    return resource


def seed_official_catalog(resource: ServiceResource) -> dict[str, str]:
    '''
        Writes the official catalogue with ids 1..n.

        Args:
            resource (ServiceResource): The mocked DynamoDB resource.

        Returns:
            dict[str, str]: Mineral id by normalized name.
    '''
    ids = {}
    for position, catalog in enumerate(OFFICIAL_MINERALS, start = 1):
        mineral_id = str(position)
        prices_dyb.put_mineral(resource, MineralItem(
            mineral_id = mineral_id,
            name = catalog['name'],
            unit = catalog['unit'],
            chemical_symbol = catalog['chemical_symbol'],
            quoted_in = catalog['quoted_in']
        ))
        ids[normalize_name(catalog['name'])] = mineral_id
    return ids
