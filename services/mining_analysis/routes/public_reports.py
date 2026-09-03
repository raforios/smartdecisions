'''
    Public, unauthenticated endpoints for the official mineral reports.

    Mirror the JWT-protected variants in routes.mining_analysis but skip
    `Depends(get_current_user)` so the institutional website (mineria.gob.bo)
    can consume them anonymously.
'''
from datetime import date as date_type
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from controllers.mining_analysis import (
    get_biweekly_history_controller,
    get_biweekly_report_controller,
    get_daily_report_controller,
)
from schemas.mining_analysis import (
    BiweeklyHistoryResponse,
    BiweeklyReportResponse,
    DailyReportResponse,
)
from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger
from services.reports_renderer import (
    build_daily_report_assets,
    build_biweekly_report_assets,
)

router = APIRouter(
    prefix = '/v1/mining-analysis/public',
    tags = ['Public Reports'],
)


PUBLIC_USER = 'public'


@router.get(
    '/reports/daily',
    response_model = DailyReportResponse,
    summary = 'Public daily mineral report (Minerales_01).',
)
async def public_daily_report(
    request: Request,
    ref_date: date_type = Query(..., alias = 'date',
                                description = 'Reference date (YYYY-MM-DD).'),
    db: Session = Depends(GET_DB_DEPENDENCY),
):
    '''Anonymous version of /reports/daily — same payload, no JWT.'''
    logger.info('Public daily report requested for %s.', ref_date)
    return await get_daily_report_controller(
        db = db, request = request, current_user = PUBLIC_USER, ref_date = ref_date,
    )


@router.get(
    '/reports/biweekly',
    response_model = BiweeklyReportResponse,
    summary = 'Public biweekly official mineral report (Minerales_02).',
)
async def public_biweekly_report(
    request: Request,
    year: int = Query(..., ge = 2000, le = 2100),
    month: int = Query(..., ge = 1, le = 12),
    half: int = Query(..., ge = 1, le = 2,
                      description = '1 = days 1-15, 2 = 16-end.'),
    db: Session = Depends(GET_DB_DEPENDENCY),
):
    '''Anonymous version of /reports/biweekly — same payload, no JWT.'''
    logger.info('Public biweekly report requested for %s-%02d Q%s.',
                year, month, half)
    return await get_biweekly_report_controller(
        db = db, request = request, current_user = PUBLIC_USER,
        year = year, month = month, half = half,
    )


@router.get(
    '/reports/biweekly/history',
    response_model = BiweeklyHistoryResponse,
    summary = 'Historical series of biweekly official cotizaciones.',
    description = 'Returns every biweekly period in the requested range that '
                  'has at least one cotización. Useful to plot historical '
                  'series in line charts.',
)
async def public_biweekly_history(
    request: Request,
    period_from: Optional[date_type] = Query(
        None, alias = 'from', description = 'Inclusive lower bound (YYYY-MM-DD).'),
    period_to: Optional[date_type] = Query(
        None, alias = 'to', description = 'Inclusive upper bound (YYYY-MM-DD).'),
    db: Session = Depends(GET_DB_DEPENDENCY),
):
    '''Anonymous endpoint feeding the historical line chart in mercados.html.'''
    logger.info('Public biweekly history requested %s → %s.', period_from, period_to)
    return await get_biweekly_history_controller(
        db = db, request = request, current_user = PUBLIC_USER,
        period_from = period_from, period_to = period_to,
    )


@router.get(
    '/reports/daily/png',
    summary = 'Daily report rendered as PNG (Minerales_01 template).',
    response_class = Response,
)
async def public_daily_png(
    request: Request,
    ref_date: date_type = Query(..., alias = 'date'),
    db: Session = Depends(GET_DB_DEPENDENCY),
):
    '''Returns the daily report rendered on the Minerales_01 template.'''
    payload = await get_daily_report_controller(
        db = db, request = request, current_user = PUBLIC_USER, ref_date = ref_date,
    )
    png_bytes, _ = build_daily_report_assets(payload, formats = ('png',))
    return Response(content = png_bytes, media_type = 'image/png')


@router.get(
    '/reports/daily/pdf',
    summary = 'Daily report rendered as PDF (Minerales_01 template).',
    response_class = Response,
)
async def public_daily_pdf(
    request: Request,
    ref_date: date_type = Query(..., alias = 'date'),
    db: Session = Depends(GET_DB_DEPENDENCY),
):
    '''Returns the daily report rendered as a single-page PDF.'''
    payload = await get_daily_report_controller(
        db = db, request = request, current_user = PUBLIC_USER, ref_date = ref_date,
    )
    _, pdf_bytes = build_daily_report_assets(payload, formats = ('pdf',))
    return Response(content = pdf_bytes, media_type = 'application/pdf')


@router.get(
    '/reports/biweekly/png',
    summary = 'Biweekly report rendered as PNG (Minerales_02 template).',
    response_class = Response,
)
async def public_biweekly_png(
    request: Request,
    year: int = Query(..., ge = 2000, le = 2100),
    month: int = Query(..., ge = 1, le = 12),
    half: int = Query(..., ge = 1, le = 2),
    db: Session = Depends(GET_DB_DEPENDENCY),
):
    '''Returns the biweekly report rendered on the Minerales_02 template.'''
    payload = await get_biweekly_report_controller(
        db = db, request = request, current_user = PUBLIC_USER,
        year = year, month = month, half = half,
    )
    png_bytes, _ = build_biweekly_report_assets(payload, formats = ('png',))
    return Response(content = png_bytes, media_type = 'image/png')


@router.get(
    '/reports/biweekly/pdf',
    summary = 'Biweekly report rendered as PDF (Minerales_02 template).',
    response_class = Response,
)
async def public_biweekly_pdf(
    request: Request,
    year: int = Query(..., ge = 2000, le = 2100),
    month: int = Query(..., ge = 1, le = 12),
    half: int = Query(..., ge = 1, le = 2),
    db: Session = Depends(GET_DB_DEPENDENCY),
):
    '''Returns the biweekly report rendered as a single-page PDF.'''
    payload = await get_biweekly_report_controller(
        db = db, request = request, current_user = PUBLIC_USER,
        year = year, month = month, half = half,
    )
    _, pdf_bytes = build_biweekly_report_assets(payload, formats = ('pdf',))
    return Response(content = pdf_bytes, media_type = 'application/pdf')
