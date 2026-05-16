'''
    PNG / PDF renderer for the official mineral reports.

    Mirrors the Streamlit-side renderer (demo/utils/mineral_reports.py) but is
    self-contained for the microservice: templates live under
    `assets/templates/` and the layout configuration is colocated here so the
    backend does not depend on the dashboard package.
'''
import io
import os
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont
from fpdf import FPDF


_ASSETS_DIR = Path(__file__).resolve().parent.parent / 'assets' / 'templates'
DAILY_TEMPLATE_PATH = str(_ASSETS_DIR / 'Minerales_01.png')
BIWEEKLY_TEMPLATE_PATH = str(_ASSETS_DIR / 'Minerales_02.png')

# Vertical centers for the 9 rows in both templates.
ROW_Y_FRACTIONS: Tuple[float, ...] = (
    0.300, 0.367, 0.434, 0.501, 0.568, 0.635, 0.702, 0.769, 0.836,
)

DAILY_COLUMN_X_FRACTIONS: Dict[str, float] = {
    'price_low':  0.54,
    'price_high': 0.71,
    'price_date': 0.85,
}
BIWEEKLY_COLUMN_X_FRACTIONS: Dict[str, float] = {
    'avg_price_low': 0.73,
}

DAILY_FONT_SIZE_FRACTION = 0.022
BIWEEKLY_FONT_SIZE_FRACTION = 0.028
SUBTITLE_FONT_SIZE_FRACTION = 0.022

TEXT_COLOR = (20, 20, 20)
FALLBACK_TEXT_COLOR = (110, 110, 110)
SUBTITLE_COLOR = (90, 90, 90)
SUBTITLE_X_FRACTION = 0.06
SUBTITLE_Y_FRACTION = 0.205

CANDIDATE_FONT_PATHS: Tuple[str, ...] = (
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf',
    '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
    '/System/Library/Fonts/Helvetica.ttc',
    '/Library/Fonts/Arial Bold.ttf',
)

MONTH_NAMES_ES = {
    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
    7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre',
    11: 'Noviembre', 12: 'Diciembre',
}


def _load_font(image_height: int, size_fraction: float) -> ImageFont.ImageFont:
    '''
    Resolves the first available TTF candidate at the requested size; falls
    back to PIL's bundled bitmap font when no system font is reachable.
    '''
    size = max(int(image_height * size_fraction), 12)
    for candidate in CANDIDATE_FONT_PATHS:
        if os.path.exists(candidate):
            try:
                return ImageFont.truetype(candidate, size = size)
            except OSError:
                continue
    return ImageFont.load_default()


def _draw_centered(
    draw: ImageDraw.ImageDraw,
    text: str,
    center: Tuple[int, int],
    font: ImageFont.ImageFont,
    color: Tuple[int, int, int],
) -> None:
    '''Centers a string around `center` using textbbox metrics.'''
    bbox = draw.textbbox((0, 0), text, font = font)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    origin = (center[0] - width // 2 - bbox[0], center[1] - height // 2 - bbox[1])
    draw.text(origin, text, font = font, fill = color)


def _format_price(value: Optional[float]) -> str:
    '''
    Two decimals for fractional values, no decimals for integer-like quotes
    (Antimonio 27,000, Wolfram 116,355). Matches the published bulletins.
    '''
    if value is None:
        return '—'
    if abs(value - round(value)) < 1e-9:
        return f'{int(round(value)):,}'
    return f'{value:,.2f}'


def _format_date(value: Any) -> str:
    '''Renders a date (or ISO string) as DD/MM/YYYY.'''
    if isinstance(value, date):
        return value.strftime('%d/%m/%Y')
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).strftime('%d/%m/%Y')
        except ValueError:
            return value
    return '—'


def _open_template(path: str) -> Image.Image:
    '''Loads a PNG template, normalizing to RGB for downstream PDF embedding.'''
    template = Image.open(path)
    if template.mode != 'RGB':
        template = template.convert('RGB')
    return template


def _draw_subtitle(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    subtitle: Optional[str],
) -> None:
    '''Optional period caption drawn between the title and the table header.'''
    if not subtitle:
        return
    _, height = image.size
    width, _ = image.size
    font = _load_font(height, SUBTITLE_FONT_SIZE_FRACTION)
    x = int(width * SUBTITLE_X_FRACTION)
    y = int(height * SUBTITLE_Y_FRACTION)
    draw.text((x, y), subtitle, font = font, fill = SUBTITLE_COLOR)


def render_daily_png(rows: List[Dict[str, Any]], subtitle: Optional[str] = None) -> bytes:
    '''Renders the daily report (Minerales_01) and returns PNG bytes.'''
    image = _open_template(DAILY_TEMPLATE_PATH)
    draw = ImageDraw.Draw(image)
    width, height = image.size
    font = _load_font(height, DAILY_FONT_SIZE_FRACTION)
    _draw_subtitle(image, draw, subtitle)

    for row, y_frac in zip(rows, ROW_Y_FRACTIONS):
        color = FALLBACK_TEXT_COLOR if row.get('is_fallback') else TEXT_COLOR
        y_px = int(height * y_frac)
        _draw_centered(draw, _format_price(row.get('price_low')),
                       (int(width * DAILY_COLUMN_X_FRACTIONS['price_low']),  y_px),
                       font, color)
        _draw_centered(draw, _format_price(row.get('price_high')),
                       (int(width * DAILY_COLUMN_X_FRACTIONS['price_high']), y_px),
                       font, color)
        _draw_centered(draw, _format_date(row.get('price_date')),
                       (int(width * DAILY_COLUMN_X_FRACTIONS['price_date']), y_px),
                       font, color)

    buffer = io.BytesIO()
    image.save(buffer, format = 'PNG', optimize = True)
    return buffer.getvalue()


def render_biweekly_png(rows: List[Dict[str, Any]], subtitle: Optional[str] = None) -> bytes:
    '''Renders the biweekly report (Minerales_02) and returns PNG bytes.'''
    image = _open_template(BIWEEKLY_TEMPLATE_PATH)
    draw = ImageDraw.Draw(image)
    width, height = image.size
    font = _load_font(height, BIWEEKLY_FONT_SIZE_FRACTION)
    _draw_subtitle(image, draw, subtitle)

    for row, y_frac in zip(rows, ROW_Y_FRACTIONS):
        color = FALLBACK_TEXT_COLOR if row.get('is_fallback') else TEXT_COLOR
        y_px = int(height * y_frac)
        x_px = int(width * BIWEEKLY_COLUMN_X_FRACTIONS['avg_price_low'])
        _draw_centered(draw, _format_price(row.get('avg_price_low')),
                       (x_px, y_px), font, color)

    buffer = io.BytesIO()
    image.save(buffer, format = 'PNG', optimize = True)
    return buffer.getvalue()


def png_to_pdf(png_bytes: bytes) -> bytes:
    '''Wraps a rendered PNG into a single-page A4 PDF.'''
    pdf = FPDF(orientation = 'P', unit = 'mm', format = 'A4')
    pdf.add_page()
    page_w, page_h = 210, 297

    image = Image.open(io.BytesIO(png_bytes))
    img_w, img_h = image.size
    aspect = img_w / img_h
    target_w = page_w - 10
    target_h = target_w / aspect
    if target_h > page_h - 10:
        target_h = page_h - 10
        target_w = target_h * aspect
    x_offset = (page_w - target_w) / 2
    y_offset = (page_h - target_h) / 2

    with tempfile.NamedTemporaryFile(suffix = '.png', delete = False) as tmp:
        tmp.write(png_bytes)
        tmp_path = tmp.name
    try:
        pdf.image(tmp_path, x = x_offset, y = y_offset, w = target_w, h = target_h)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    output = pdf.output(dest = 'S')
    if isinstance(output, str):
        return output.encode('latin-1')
    return bytes(output)


def _model_to_dict(payload: Any) -> Dict[str, Any]:
    '''Best-effort conversion of pydantic models / dicts to a plain dict.'''
    if hasattr(payload, 'model_dump'):
        return payload.model_dump()
    if isinstance(payload, dict):
        return payload
    raise TypeError(f'Unsupported payload type for renderer: {type(payload)!r}')


def build_daily_report_assets(
    payload: Any,
    formats: Iterable[str] = ('png', 'pdf'),
) -> Tuple[Optional[bytes], Optional[bytes]]:
    '''
    Renders the daily report into the requested formats and returns
    (png_bytes, pdf_bytes). Either entry is None when its format is skipped.
    '''
    data = _model_to_dict(payload)
    subtitle = f'Diario al {_format_date(data.get("ref_date"))}'
    png_bytes = render_daily_png(data['rows'], subtitle = subtitle)
    fmts = set(formats)
    pdf_bytes = png_to_pdf(png_bytes) if 'pdf' in fmts else None
    return (png_bytes if 'png' in fmts else None, pdf_bytes)


def build_biweekly_report_assets(
    payload: Any,
    formats: Iterable[str] = ('png', 'pdf'),
) -> Tuple[Optional[bytes], Optional[bytes]]:
    '''
    Renders the biweekly report into the requested formats and returns
    (png_bytes, pdf_bytes). Either entry is None when its format is skipped.
    '''
    data = _model_to_dict(payload)
    month = int(data['month'])
    year = int(data['year'])
    half = int(data['half'])
    subtitle = f'Oficial quincenal — {MONTH_NAMES_ES[month]} {year} (Q{half})'
    png_bytes = render_biweekly_png(data['rows'], subtitle = subtitle)
    fmts = set(formats)
    pdf_bytes = png_to_pdf(png_bytes) if 'pdf' in fmts else None
    return (png_bytes if 'png' in fmts else None, pdf_bytes)
