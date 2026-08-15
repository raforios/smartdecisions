'''
    Shared builders for the entry / request report rows.

    The dashboard feed and the kardex reports present the same two lists —
    Notas de Ingreso and supply requests — with the same per-document line
    count. Keeping one implementation here means a change to what a report row
    shows (or to how the counts are queried) lands in both places at once.

    The counts are resolved with a single grouped query per list instead of one
    per document, which is what keeps these reports usable as the warehouse
    history grows.
'''
from typing import Dict, Iterable, List, Sequence

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.supplies import Entry, EntryDetail, Request, RequestDetail
from schemas.kardex import EntryReportRowSchema, RequestReportRowSchema

# SQLAlchemy builds `func.count` dynamically, which Pylint cannot resolve and
# reports as not-callable. The call is correct; the checker is not.
# pylint: disable=not-callable


def count_entry_lines(db: Session, entry_ids: Sequence[int]) -> Dict[int, int]:
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


def count_request_items(db: Session, request_ids: Sequence[int]) -> Dict[int, int]:
    '''
        Counts requested items per request in one grouped query.

        Args:
            db (Session): Active database session.
            request_ids (Sequence[int]): Requests to count items for.

        Returns:
            Dict[int, int]: Item count indexed by request id.
    '''
    if not request_ids:
        return {}
    rows = (
        db.query(RequestDetail.request_id, func.count(RequestDetail.id))
        .filter(RequestDetail.request_id.in_(request_ids))
        .group_by(RequestDetail.request_id)
        .all()
    )
    return dict(rows)


def build_entry_rows(db: Session, entries: Iterable[Entry]) -> List[EntryReportRowSchema]:
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


def build_request_rows(db: Session, requests: Iterable[Request]) -> List[RequestReportRowSchema]:
    '''
        Maps supply requests into report rows, resolving their item counts in a
        single query.

        Args:
            db (Session): Active database session.
            requests (Iterable[Request]): Requests already filtered and ordered.

        Returns:
            List[RequestReportRowSchema]: One row per request, in the given order.
    '''
    records = list(requests)
    counts = count_request_items(db, [record.id for record in records])
    return [
        RequestReportRowSchema(
            request_id = record.id,
            code = record.code,
            requester_email = record.requester_email,
            status = record.status,
            total_items = counts.get(record.id, 0),
            requested_at = record.requested_at,
            closed_at = record.closed_at,
        )
        for record in records
    ]
