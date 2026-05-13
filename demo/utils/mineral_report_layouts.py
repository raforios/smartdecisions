'''
    Layout configuration for the Minerales_01 / Minerales_02 templates.

    Coordinates are expressed as fractions of image width/height so the same
    config works regardless of the underlying template resolution. Adjust here
    if a value sits off-grid in the rendered PNG; the renderer reads this
    module on every call.
'''
from typing import Dict, List, Tuple


# Vertical centers for the 9 mineral rows (top → bottom), shared by both
# templates because the body grid is identical.
ROW_Y_FRACTIONS: List[float] = [
    0.300,  # Estaño
    0.367,  # Plomo
    0.434,  # Zinc
    0.501,  # Cobre
    0.568,  # Antimonio
    0.635,  # Wolfram
    0.702,  # Bismuto
    0.769,  # Oro
    0.836,  # Plata
]

# Minerales_01 — daily report (three value columns).
DAILY_COLUMN_X_FRACTIONS: Dict[str, float] = {
    'price_low':  0.54,   # column BAJA
    'price_high': 0.71,   # column ALTA
    'price_date': 0.85,   # column FECHA (pulled in 2% to clear the right gutter)
}

# Minerales_02 — biweekly official report (single value column).
BIWEEKLY_COLUMN_X_FRACTIONS: Dict[str, float] = {
    'avg_price_low': 0.73,
}

# Font size as a fraction of image height. The daily template fits three
# value columns plus a date, so it uses a slightly smaller body to keep
# six-digit figures (Wolfram 116,355) from colliding into the next column.
DAILY_FONT_SIZE_FRACTION: float = 0.022
BIWEEKLY_FONT_SIZE_FRACTION: float = 0.028

TEXT_COLOR: Tuple[int, int, int] = (20, 20, 20)
FALLBACK_TEXT_COLOR: Tuple[int, int, int] = (110, 110, 110)

# Optional subtitle drawn between the title ("COTIZACIÓN DE MINERALES") and
# the table header. Coordinates are top-left anchored fractions of the image.
SUBTITLE_X_FRACTION: float = 0.06
SUBTITLE_Y_FRACTION: float = 0.205
SUBTITLE_FONT_SIZE_FRACTION: float = 0.022
SUBTITLE_COLOR: Tuple[int, int, int] = (90, 90, 90)


# Ordered list of system font paths probed by the renderer. The first match
# wins; the final empty string forces PIL's default bitmap font as a safety
# net for headless Linux containers without proper TTFs installed.
CANDIDATE_FONT_PATHS: Tuple[str, ...] = (
    '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
    '/System/Library/Fonts/Helvetica.ttc',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf',
    '/Library/Fonts/Arial Bold.ttf',
    '',
)
