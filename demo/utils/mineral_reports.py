'''
    Renderers for the official Minerales_01 (daily) and Minerales_02 (biweekly)
    mineral cotización reports.

    Strategy: open the curated PNG template, draw values on top with Pillow at
    coordinates defined in mineral_report_layouts. The PDF variant embeds the
    rendered PNG as a single page so layout and design stay byte-identical
    across formats.
'''
import io
import os
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont
from fpdf import FPDF

from utils.mineral_report_layouts import (
    BIWEEKLY_COLUMN_X_FRACTIONS,
    BIWEEKLY_FONT_SIZE_FRACTION,
    CANDIDATE_FONT_PATHS,
    DAILY_COLUMN_X_FRACTIONS,
    DAILY_FONT_SIZE_FRACTION,
    FALLBACK_TEXT_COLOR,
    ROW_Y_FRACTIONS,
    SUBTITLE_COLOR,
    SUBTITLE_FONT_SIZE_FRACTION,
    SUBTITLE_X_FRACTION,
    SUBTITLE_Y_FRACTION,
    TEXT_COLOR,
)


def _load_font(image_height: int, size_fraction: float) -> ImageFont.ImageFont:
    '''
    Resolves the first available TTF candidate at the requested size. Falls
    back to PIL's bundled bitmap font when no system font is present (e.g.
    minimal Docker images) so rendering never raises.
    '''
    size = max(int(image_height * size_fraction), 12)
    for candidate in CANDIDATE_FONT_PATHS:
        if not candidate:
            continue
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
    '''
    Centers `text` around `center` using textbbox so multi-line and ascender
    overshoot are handled correctly across font versions.
    '''
    bbox = draw.textbbox((0, 0), text, font = font)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    origin = (center[0] - width // 2 - bbox[0], center[1] - height // 2 - bbox[1])
    draw.text(origin, text, font = font, fill = color)


# Bulletins publish two decimals; the source keeps four.
_PRICE_QUANTUM: Decimal = Decimal('0.01')


def _format_price(value: float) -> str:
    '''
    Renders prices with two decimals when fractional, no decimals when integral.

    Antimonio / Wolfram quotes arrive as whole numbers (27000, 116355) while
    Oro keeps two decimals (4710.55); this rule lets the same formatter handle
    both without padding zeros on integers.

    Rounds HALF_UP through Decimal, never with float formatting: prices are
    stored with four decimals, and `f'{12.825:.2f}'` yields 12.82 because the
    binary float behind that literal is 12.8249999…. A published bulletin
    cannot round a half down.
    '''
    if value is None:
        return '—'
    amount = Decimal(str(value)).quantize(_PRICE_QUANTUM, rounding = ROUND_HALF_UP)
    if amount == amount.to_integral_value():
        return f'{int(amount):,}'
    return f'{amount:,.2f}'


def _format_date(value: Any) -> str:
    '''
    Renders a date or ISO-date string as DD/MM/YYYY.
    '''
    if isinstance(value, date):
        return value.strftime('%d/%m/%Y')
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).strftime('%d/%m/%Y')
        except ValueError:
            return value
    return '—'


def _open_template(template_path: str) -> Image.Image:
    '''
    Loads the template PNG ensuring an RGB canvas to keep PDF embedding happy.
    '''
    template = Image.open(template_path)
    if template.mode != 'RGB':
        template = template.convert('RGB')
    return template


def _draw_subtitle(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    subtitle: Optional[str],
) -> None:
    '''
    Draws the period subtitle (e.g. "Oficial quincenal — Mayo 2026 (Q1)") in
    the empty band between the main title and the table header. Skipped when
    `subtitle` is empty or None.
    '''
    if not subtitle:
        return
    width, height = image.size
    font = _load_font(height, SUBTITLE_FONT_SIZE_FRACTION)
    x = int(width * SUBTITLE_X_FRACTION)
    y = int(height * SUBTITLE_Y_FRACTION)
    draw.text((x, y), subtitle, font = font, fill = SUBTITLE_COLOR)


def render_daily_report_png(
    rows: List[Dict[str, Any]],
    template_path: str,
    subtitle: Optional[str] = None,
) -> bytes:
    '''
    Renders Minerales_01 (daily report) and returns the resulting PNG bytes.

    Args:
        rows (List[Dict]): One dict per mineral matching DailyMineralPriceRow.
            Order is significant — it must match the template's row layout.
        template_path (str): Filesystem path to Minerales_01.png.
        subtitle (Optional[str]): Period caption drawn under the title (e.g.
            "Diario al 30/04/2026"). Omitted when None or empty.

    Returns:
        bytes: PNG-encoded image with values drawn on top.
    '''
    image = _open_template(template_path)
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


def render_biweekly_report_png(
    rows: List[Dict[str, Any]],
    template_path: str,
    subtitle: Optional[str] = None,
) -> bytes:
    '''
    Renders Minerales_02 (biweekly official report) and returns PNG bytes.

    Args:
        rows (List[Dict]): One dict per mineral matching BiweeklyMineralPriceRow.
        template_path (str): Filesystem path to Minerales_02.png.
        subtitle (Optional[str]): Period caption drawn under the title (e.g.
            "Oficial quincenal — Mayo 2026 (Q1)"). Omitted when None or empty.

    Returns:
        bytes: PNG-encoded image with the official quincenal averages drawn on top.
    '''
    image = _open_template(template_path)
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
    '''
    Wraps a rendered PNG into a single-page A4 PDF. The PNG is centered and
    scaled to fit while preserving its aspect ratio so the layout reproduces
    one-to-one against the source template.
    '''
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

    # FPDF reads images by path; write to a temp file because the in-memory
    # API is version-dependent across FPDF / fpdf2.
    import tempfile
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


def thumbnail_png(png_bytes: bytes, max_width: int = 900) -> bytes:
    '''
    Returns a downsized PNG preview for inline Streamlit display so the
    browser does not load the multi-megapixel master.
    '''
    image = Image.open(io.BytesIO(png_bytes))
    if image.width <= max_width:
        return png_bytes
    aspect = image.height / image.width
    new_size = (max_width, int(max_width * aspect))
    preview = image.resize(new_size, Image.LANCZOS)
    buffer = io.BytesIO()
    preview.save(buffer, format = 'PNG', optimize = True)
    return buffer.getvalue()
