'''
    Shared builder for the entry report rows.

    The dashboard feed and the kardex reports present the same list of Notas
    de Ingreso with the same per-document line count. Keeping one
    implementation here means a change to what a report row shows (or to how
    the counts are queried) lands in both places at once.

    The counts are resolved with a single grouped query per list instead of one
    per document, which is what keeps these reports usable as the warehouse
    history grows.
'''
from typing import Dict, Iterable, List, Sequence

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.supplies import Entry, EntryDetail
from schemas.kardex import EntryReportRowSchema

# SQLAlchemy builds `func.count` dynamically, which Pylint cannot resolve and
# reports as not-callable. The call is correct; the checker is not.
# pylint: disable=not-callable


def count_entry_lines(
    db: Session,
    entry_ids: Sequence[int]
) -> Dict[int, int]:
    '''
        Counts detail lines per entry in one grouped query.

        Args:
            db (Session): Active database session.
            entry_ids (Sequence[int]): Entries to count lines for.

        Returns:
            Dict[int, int]: Line count indexed by entry id; entries without
                details are simply absent.
    '''
    if not entry_ids:
        return {}
    rows = (
        db.query(EntryDetail.entry_id, func.count(EntryDetail.id))
        .filter(EntryDetail.entry_id.in_(entry_ids))
        .group_by(EntryDetail.entry_id)
        .all()
    )
    return dict(rows)


def build_entry_rows(
    db: Session,
    entries: Iterable[Entry]
) -> List[EntryReportRowSchema]:
    '''
        Maps Nota de Ingreso records into report rows, resolving their line
        counts in a single query.

        Args:
            db (Session): Active database session.
            entries (Iterable[Entry]): Entries already filtered and ordered.

        Returns:
            List[EntryReportRowSchema]: One row per entry, in the given order.
    '''
    records = list(entries)
    line_counts = count_entry_lines(db, [record.id for record in records])
    return [
        EntryReportRowSchema(
            entry_id = record.id,
            code = record.code,
            entry_type = record.entry_type,
            supplier = record.supplier,
            total_lines = line_counts.get(record.id, 0),
            subtotal = record.subtotal,
            discount = record.discount,
            total = record.total,
            created_at = record.created_at,
        )
        for record in records
    ]
