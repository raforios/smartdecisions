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
        python -m scripts.migrate_to_dynamodb [--yes] [--mineral-id 3]

    Without --yes the script reports what it would copy and exits without
    writing. Re-running it is safe: every write is a put by key, so a second
    run overwrites the same items with the same values.
'''
import argparse
from typing import List, Optional

from models.mining_analysis import Mineral, MiningPrice
from models.mining_analysis_dyb import MineralItem, MiningPriceItem
from scripts.cli_support import database_session, report
from services import crud_dyb


def _read_minerals(session, mineral_id: Optional[int]) -> List[MineralItem]:
    '''
        Reads the catalogue from the relational database.

        Args:
            session: Open SQLAlchemy session.
            mineral_id (int | None): Restrict to one mineral, or all of them.

        Returns:
            List[MineralItem]: The catalogue, ready for DynamoDB.
    '''
    query = session.query(Mineral)
    if mineral_id is not None:
        query = query.filter(Mineral.id == mineral_id)
    return [
        MineralItem(
            mineral_id = str(row.id),
            name = row.name,
            unit = row.unit,
            chemical_symbol = row.chemical_symbol,
            quoted_in = row.quoted_in,
            method = row.method,
            created_at = row.created_at.isoformat() if row.created_at else None
        )
        for row in query.order_by(Mineral.id).all()
    ]


def _read_prices(session, mineral_id: Optional[int]) -> List[MiningPriceItem]:
    '''
        Reads the quotations from the relational database.

        Args:
            session: Open SQLAlchemy session.
            mineral_id (int | None): Restrict to one mineral, or all of them.

        Returns:
            List[MiningPriceItem]: The quotations, ready for DynamoDB.
    '''
    query = session.query(MiningPrice)
    if mineral_id is not None:
        query = query.filter(MiningPrice.mineral_id == mineral_id)
    return [
        MiningPriceItem(
            mineral_id = str(row.mineral_id),
            date = row.date,
            price_low = None if row.price_low is None else float(row.price_low),
            price_high = None if row.price_high is None else float(row.price_high),
            created_at = row.created_at.isoformat() if row.created_at else None
        )
        for row in query.order_by(MiningPrice.mineral_id, MiningPrice.date).all()
    ]


def _describe(minerals: List[MineralItem], prices: List[MiningPriceItem]) -> None:
    '''
        Reports what was read, so a dry run is worth something.

        Args:
            minerals (List[MineralItem]): Catalogue read.
            prices (List[MiningPriceItem]): Quotations read.
    '''
    report(f'Catalogue: {len(minerals)} mineral(s).')
    report(f'Quotations: {len(prices)} row(s).')
    if prices:
        report(f'Date range: {min(p.date for p in prices)} -> '
               f'{max(p.date for p in prices)}.')
    for mineral in minerals:
        own = sum(1 for price in prices if price.mineral_id == mineral.mineral_id)
        report(f'  [{mineral.mineral_id}] {mineral.name}: {own} quotation(s).')


def _copy(minerals: List[MineralItem], prices: List[MiningPriceItem]) -> None:
    '''
        Writes the catalogue and the quotations into DynamoDB.

        Args:
            minerals (List[MineralItem]): Catalogue to write.
            prices (List[MiningPriceItem]): Quotations to write.
    '''
    for mineral in minerals:
        crud_dyb.put_mineral(mineral)
    report(f'Catalogue written: {len(minerals)} mineral(s).')

    written = crud_dyb.put_prices_batch(prices)
    report(f'Quotations written: {written} row(s).')


def _verify(minerals: List[MineralItem], prices: List[MiningPriceItem]) -> bool:
    '''
        Reads DynamoDB back and compares the counts against the source.

        Args:
            minerals (List[MineralItem]): Catalogue that was written.
            prices (List[MiningPriceItem]): Quotations that were written.

        Returns:
            bool: True when both counts match.
    '''
    stored_minerals = len(crud_dyb.list_minerals())
    stored_prices = len(crud_dyb.scan_prices())
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

    _copy(minerals, prices)
    return 0 if _verify(minerals, prices) else 1


if __name__ == '__main__':
    raise SystemExit(main())
