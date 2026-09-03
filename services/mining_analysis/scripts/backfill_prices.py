'''
    Backfill script: wipes t_mining_prices and re-ingests from a clean source.

    Required because the legacy clean_currency_pro stripped anglo decimal
    dots, corrupting values such as Bismuto `17.54` → `1754` in the database.
    Run AFTER deploying the fix. Idempotent: re-running with the same source
    yields the same final state.

    Usage:
        python -m scripts.backfill_prices \\
            --source /path/to/cotizaciones_min.xlsx \\
            [--delimiter ,] [--yes]

    Without --yes the script prints the planned actions and exits without
    touching the database.
'''
import argparse
import asyncio
from pathlib import Path

from sqlalchemy import text

from scripts.cli_support import database_session, report, source_is_missing
from services.mining_analysis import process_mining_etl_service


def _truncate_prices(session) -> int:
    '''
    Removes every row from t_mining_prices and returns the deleted count.
    Catalog tables (t_minerals) are preserved so foreign keys stay valid.
    '''
    deleted = session.execute(text('SELECT COUNT(*) FROM t_mining_prices')).scalar() or 0
    session.execute(text('DELETE FROM t_mining_prices'))
    session.commit()
    return int(deleted)


async def _reingest(session, source: Path, delimiter: str) -> dict:
    '''
    Reads the source file and runs the fixed ETL against the open session.
    '''
    file_content = source.read_bytes()
    return await process_mining_etl_service(
        db = session,
        file_content = file_content,
        file_name = source.name,
        delimiter = delimiter
    )


def main() -> int:
    '''
    Entry point. Parses CLI args, optionally prompts, and runs the backfill.
    '''
    parser = argparse.ArgumentParser(description = 'Backfill t_mining_prices.')
    parser.add_argument('--source', required = True, type = Path,
                        help = 'Path to the clean cotizaciones xlsx/csv to re-ingest.')
    parser.add_argument('--delimiter', default = ',',
                        help = 'CSV delimiter (ignored for xlsx). Defaults to ",".')
    parser.add_argument('--yes', action = 'store_true',
                        help = 'Skip confirmation prompt and execute.')
    args = parser.parse_args()

    if source_is_missing(args.source):
        return 2

    if not args.yes:
        print('DRY-RUN: would DELETE every row in t_mining_prices and re-ingest from '
              f'{args.source}. Re-run with --yes to apply.')
        return 0

    with database_session() as session:
        deleted = _truncate_prices(session)
        message = f'Backfill: deleted {deleted} rows from t_mining_prices.'
        report(message)

        result = asyncio.run(_reingest(session, args.source, args.delimiter))
        message = f'Backfill: {result}'
        report(message)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
