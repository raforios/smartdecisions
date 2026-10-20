'''
    Migration script: copies the catalogue and the quotations from the
    relational database into DynamoDB.

    The ETL loads MySQL, and the deployed service runs on DynamoDB because no
    RDS is provisioned. Until the history is copied across, the Lambda answers
    correctly over an empty table, which is worse than failing: the charts come
    back blank and nothing says why.

    The identifier is the one point worth being careful about. On the relational
    path the service exposes `str(row.id)`, so the same numeric identifier is
    used as the DynamoDB partition key. Anything else would make the two
    backends disagree about which mineral is which.

    Usage:
        python -m tools.etl_minerals.migrate_to_dynamodb [--yes] [--mineral-id 3]

    Without --yes the script reports what it would copy and exits without
    writing. Re-running it is safe: every write is a put by key, so a second
    run overwrites the same items with the same values.
'''
import argparse
import decimal
from typing import Any

from boto3.resources.base import ServiceResource
from sqlalchemy.orm import Session

from tools.etl_minerals.connection import database_session, dynamodb, environment, report
from tools.etl_minerals.models import Mineral, MiningPrice

# The items keep the shape the API reads (models/mining_analysis_dyb.py):
# the numeric identifier as a string key, the date as an ISO sort key.
MineralItem = dict[str, Any]
MiningPriceItem = dict[str, Any]


def _decimals(item: dict[str, Any]) -> dict[str, Any]:
    '''
        DynamoDB takes no float: every float goes as a Decimal of its text.

        Args:
            item (dict[str, Any]): Item to store.

        Returns:
            dict[str, Any]: The same item, floats converted.
    '''
    return {key: decimal.Decimal(str(value)) if isinstance(value, float) else value
            for key, value in item.items()}


def _scan_count(
    dynamodb_resource: ServiceResource,
    table_name: str
) -> int:
    '''
        How many items a table holds, paging through the scan.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            table_name (str): Table to count.

        Returns:
            int: Item count.
    '''
    table = dynamodb_resource.Table(table_name)
    total, kwargs = 0, {'Select': 'COUNT'}
    while True:
        response = table.scan(**kwargs)
        total += response['Count']
        if not response.get('LastEvaluatedKey'):
            return total
        kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']


def _write(
    dynamodb_resource: ServiceResource,
    table_name: str,
    items: list[dict[str, Any]]
) -> int:
    '''
        Writes items in one batch, replacing any row with the same key.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            table_name (str): Target table.
            items (list[dict[str, Any]]): Items to write.

        Returns:
            int: How many were written.
    '''
    with dynamodb_resource.Table(table_name).batch_writer() as batch:
        for item in items:
            batch.put_item(Item = _decimals(item))
    return len(items)


def _read_minerals(
    session: Session,
    mineral_id: int | None
) -> list[MineralItem]:
    '''
        Reads the catalogue from the relational database.

        Args:
            session: Open SQLAlchemy session.
            mineral_id (int | None): Restrict to one mineral, or all of them.

        Returns:
            list[MineralItem]: The catalogue, ready for DynamoDB.
    '''
    query = session.query(Mineral)
    if mineral_id is not None:
        query = query.filter(Mineral.id == mineral_id)
    return [
        {
            'mineral_id': str(row.id),
            'name': row.name,
            'unit': row.unit,
            'chemical_symbol': row.chemical_symbol,
            'quoted_in': row.quoted_in,
            'method': row.method,
            'created_at': row.created_at.isoformat() if row.created_at else None
        }
        for row in query.order_by(Mineral.id).all()
    ]


def _read_prices(
    session: Session,
    mineral_id: int | None
) -> list[MiningPriceItem]:
    '''
        Reads the quotations from the relational database.

        Args:
            session: Open SQLAlchemy session.
            mineral_id (int | None): Restrict to one mineral, or all of them.

        Returns:
            list[MiningPriceItem]: The quotations, ready for DynamoDB.
    '''
    query = session.query(MiningPrice)
    if mineral_id is not None:
        query = query.filter(MiningPrice.mineral_id == mineral_id)
    return [
        {
            'mineral_id': str(row.mineral_id),
            'date': row.date.isoformat(),
            'price_low': None if row.price_low is None else float(row.price_low),
            'price_high': None if row.price_high is None else float(row.price_high),
            'created_at': row.created_at.isoformat() if row.created_at else None
        }
        for row in query.order_by(MiningPrice.mineral_id, MiningPrice.date).all()
    ]


def _describe(
    minerals: list[MineralItem],
    prices: list[MiningPriceItem]
) -> None:
    '''
        Reports what was read, so a dry run is worth something.

        Args:
            minerals (list[MineralItem]): Catalogue read.
            prices (list[MiningPriceItem]): Quotations read.
    '''
    report(f'Catalogue: {len(minerals)} mineral(s).')
    report(f'Quotations: {len(prices)} row(s).')
    if prices:
        report(f'Date range: {min(p["date"] for p in prices)} -> '
               f'{max(p["date"] for p in prices)}.')
    for mineral in minerals:
        own = sum(1 for price in prices if price['mineral_id'] == mineral['mineral_id'])
        report(f'  [{mineral["mineral_id"]}] {mineral["name"]}: {own} quotation(s).')


def _copy(
    dynamodb_resource: ServiceResource,
    minerals: list[MineralItem],
    prices: list[MiningPriceItem]
) -> None:
    '''
        Writes the catalogue and the quotations into DynamoDB.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            minerals (list[MineralItem]): Catalogue to write.
            prices (list[MiningPriceItem]): Quotations to write.
    '''
    env = environment()
    _write(dynamodb_resource, env['DYNAMODB_TABLE_NAME_MINERALS'], minerals)
    report(f'Catalogue written: {len(minerals)} mineral(s).')

    written = _write(dynamodb_resource, env['DYNAMODB_TABLE_NAME_MINING_PRICES'], prices)
    report(f'Quotations written: {written} row(s).')


def _verify(
    dynamodb_resource: ServiceResource,
    minerals: list[MineralItem],
    prices: list[MiningPriceItem]
) -> bool:
    '''
        Reads DynamoDB back and compares the counts against the source.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            minerals (list[MineralItem]): Catalogue that was written.
            prices (list[MiningPriceItem]): Quotations that were written.

        Returns:
            bool: True when both counts match.
    '''
    env = environment()
    stored_minerals = _scan_count(dynamodb_resource, env['DYNAMODB_TABLE_NAME_MINERALS'])
    stored_prices = _scan_count(dynamodb_resource, env['DYNAMODB_TABLE_NAME_MINING_PRICES'])
    report(f'Verification: {stored_minerals} mineral(s), {stored_prices} quotation(s) '
           f'in DynamoDB.')
    return stored_minerals >= len(minerals) and stored_prices >= len(prices)


def main() -> int:
    '''
        Entry point of the migration.

        Returns:
            int: 0 on success, 1 when the verification does not add up.
    '''
    parser = argparse.ArgumentParser(
        description = 'Copies minerals and quotations from SQL into DynamoDB.'
    )
    parser.add_argument('--yes', action = 'store_true',
                        help = 'Actually write. Without it the script only reports.')
    parser.add_argument('--mineral-id', type = int, default = None,
                        help = 'Restrict the copy to a single mineral.')
    args = parser.parse_args()

    with database_session() as session:
        minerals = _read_minerals(session, args.mineral_id)
        prices = _read_prices(session, args.mineral_id)

    _describe(minerals, prices)

    if not args.yes:
        report('Dry run: nothing was written. Re-run with --yes to copy.')
        return 0

    if not minerals:
        report('Nothing to copy: the relational catalogue is empty.')
        return 1

    dynamodb_resource = dynamodb()
    _copy(dynamodb_resource, minerals, prices)
    return 0 if _verify(dynamodb_resource, minerals, prices) else 1


if __name__ == '__main__':
    raise SystemExit(main())
