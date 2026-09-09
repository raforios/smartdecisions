'''
    Demo / test dataset builder for SmartDecisions.

    Turns the real distributor export (`data/DetalleVentas.csv`) into a sample
    file that matches the client-facing template served by INGEST, so the same
    artifact works as (a) a fast fixture for local testing and (b) the example
    we hand to a prospect to show the data we need from them.

    Five things the source file cannot do on its own are fixed here:

      1. **No cost column.** A unit cost is derived from a per-category gross
         margin so the margin KPIs have something to chew on. It is synthetic
         and the workbook says so on its 'Origen de los datos' sheet.
      2. **Only four months, the last one partial.** The partial month is cut
         (it would render as a fake sales collapse in the trend chart) and the
         history is extended backwards with trend, seasonality and noise.
      3. **Placeholder coordinates.** Rows whose GPS reading is a literal 0 are
         dropped, so the route map never leaves the client's city.
      4. **Real client, vendor and brand names.** All are replaced or stripped;
         the data was shared for a different engagement and must not travel
         inside a demo.
      5. **A static roster.** Cloning one real month over and over gives every
         month the same clients, so the portfolio module reports zero movement.
         Each client gets a lifecycle instead — when they join, whether they
         churn, whether they go quiet and return, how often they buy and whether
         their spend grows or fades. Calibrated against the source file's own
         month-over-month retention (82%), not against a guess.

    Sampling is done **by client, never by row**: a random subset of rows would
    break the invoices into fragments and the affinity engine would find no
    baskets. Whole invoices of whole clients are kept.

    Usage:
        python tools/build_sample_dataset.py                  # both artifacts
        python tools/build_sample_dataset.py --rows 2000 --months 3 \
            --output tools/samples/ventas_muestra_2k.xlsx
'''
import argparse
import unicodedata
from dataclasses import dataclass, field
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


# --- Source contract -------------------------------------------------------

SOURCE_PATH: Path = Path('../data/DetalleVentas.xlsx')
SOURCE_DELIMITER: str = ';'  # only used when the source is a .csv export

# Only the source columns we actually carry into the sample.
SOURCE_COLUMNS: dict[str, str] = {
    'Fecha': 'fecha',
    'Canal': 'canal',
    'Region': 'region',
    'Numero Factura': 'factura',
    'Cliente ID': 'cliente_id',
    'Cliente': 'cliente',
    'Zona': 'zona',
    'Ciudad': 'ciudad',
    'Vendedor': 'vendedor',
    'Ruta Id': 'ruta_id',
    'Latitud': 'latitud',
    'Longitud': 'longitud',
    'Codigo Sap': 'producto_id',
    'Producto': 'producto',
    'Categoria': 'categoria',
    'Unidades': 'cantidad',
    'Monto Final': 'monto',
}

# Internal name -> template header. The header side is NOT restated here: it is
# read from the ingest contract (schemas.ingest.SALES_COLUMNS), so a column added
# there shows up in the sample without touching this file.
_INTERNAL_TO_CANONICAL: dict[str, str] = {
    'fecha': 'date',
    'factura': 'order_id',
    'cliente': 'pos_name',
    'zona': 'zone',
    'ciudad': 'city',
    'region': 'region',
    'canal': 'channel',
    'vendedor': 'seller',
    'latitud': 'latitude',
    'longitud': 'longitude',
    'producto': 'product_name',
    'categoria': 'category',
    'cantidad': 'quantity',
    'precio_unitario': 'unit_price',
    'costo_unitario': 'unit_cost',
    'monto_total': 'total_amount',
}


def _template_headers() -> dict[str, str]:
    '''
        Builds {internal name: template header} from the ingest contract.

        Returns:
            dict[str, str]: Mapping in the contract's own column order.
    '''
    sys.path.insert(0, str(Path('services/ingest').resolve()))
    from schemas.ingest import TEMPLATE_COLUMNS # pylint: disable=import-outside-toplevel

    canonical_to_header = {column.canonical: column.header for column in TEMPLATE_COLUMNS}
    return {
        internal: canonical_to_header[canonical]
        for internal, canonical in _INTERNAL_TO_CANONICAL.items()
        if canonical in canonical_to_header
    }


TEMPLATE_HEADERS: dict[str, str] = _template_headers()


# --- Synthesis parameters --------------------------------------------------

# Gross margin by category, typical of Bolivian consumer-goods distribution.
# Drives the derived unit cost: costo = precio * (1 - margen).
CATEGORY_MARGINS: dict[str, float] = {
    'CAFES': 0.30,
    'CHOCOLATES': 0.28,
    'WAFER': 0.26,
    'RELLENAS': 0.25,
    'PLANAS DULCES': 0.24,
    'PLANAS SALADAS': 0.24,
    'PLANAS SALUD': 0.27,
    'BEBIDAS': 0.18,
    'LACTEOS': 0.15,
    'CULINARIOS': 0.22,
    'NUTRICION': 0.32,
    'CPW': 0.29,
    'PANETONES': 0.20,
}
DEFAULT_MARGIN: float = 0.22

# Per-product margin jitter (+/- this, in margin points) so the ABC / margin
# ranking is not a flat block per category.
MARGIN_JITTER: float = 0.03

# Demand index of each calendar month RELATIVE TO JANUARY. The three months
# present in the source (Nov, Dec, Jan) keep their real level: they are
# themselves, and scaling them would double-count their own seasonality.
MONTH_SEASONALITY: dict[int, float] = {
    1: 1.00, 2: 0.88, 3: 0.95, 4: 0.93, 5: 0.98, 6: 1.00,
    7: 1.05, 8: 1.00, 9: 0.97, 10: 1.03, 11: 1.00, 12: 1.00,
}

# Categories that only sell in specific calendar months. Panetón is a
# Christmas product in Bolivia; leaving it flat all year would be the kind of
# detail that costs credibility in front of a commercial manager.
SEASONAL_CATEGORIES: dict[str, set[int]] = {
    'PANETONES': {11, 12},
}

# Compounding month-over-month factors applied backwards from the newest month,
# so older months are smaller and cheaper. Gives Growth and the price-drift KPI
# a real signal to report instead of flat lines.
MONTHLY_GROWTH: float = 0.008
MONTHLY_INFLATION: float = 0.004
DEMAND_NOISE: float = 0.06

# --- Client lifecycles -----------------------------------------------------

# A real book of business is not a fixed roster: it gains clients, loses others,
# and some go quiet and come back. Without this the portfolio-health module has
# nothing to report — every month shows the same clients and zero movement.
LIFECYCLE_MIX: dict[str, float] = {
    'leal': 0.60,        # buys across the whole period
    'nuevo': 0.18,       # joins partway through (acquisition)
    'perdido': 0.09,     # stops buying partway through (churn)
    'recuperado': 0.13,  # goes dormant for a stretch, then returns
}

# Probability that an active client places an order in a given month.
# Calibrated against the source export, where 82% of the clients active in one
# month are still active the next (18-20% month-over-month churn). Guessing here
# is what produced first a 6% churn and then a 37% one, neither of them real.
ACTIVITY_RANGE: tuple[float, float] = (0.74, 0.90)

# Each client's own month-over-month multiplier: some grow, some fade. This is
# what produces partial declines in the at-risk list instead of only clients who
# vanished outright.
CLIENT_TREND_RANGE: tuple[float, float] = (0.955, 1.045)

# Months a 'recuperado' client stays dormant before coming back.
DORMANT_SPAN: tuple[int, int] = (2, 4)

# Below this many months a lifecycle cannot be expressed: a churn window and a
# dormant stretch would not fit, and the file would come out nearly empty.
_MIN_MONTHS_FOR_LIFECYCLES: int = 8

# Average share of client-months that survive the lifecycle filter. Used to size
# the client pool so `--rows` still lands near the requested figure.
_EXPECTED_ACTIVITY: float = 0.74

# Brand tokens stripped from product descriptions. The generic descriptor
# ('Bombón 15(50x8g)') carries all the analytical meaning; the brand carries
# only the confidentiality problem.
BRAND_TOKENS: tuple[str, ...] = (
    'NESTLE', 'NESTLÉ', 'SUBLIME', 'MCKAY', 'MC KAY', 'GAUCHITA', 'NESCAFE',
    'NESCAFÉ', 'MILO', 'MAGGI', 'NIDO', 'NAN', 'KLIM', 'SAVORA', 'NESQUIK',
    'NESTUM', 'CHOCAPIC', 'TRIX', 'FITNESS', 'LA LECHERA', 'CARNAVAL',
)

# Name pools for anonymization: Bolivian first / last names.
FIRST_NAMES: tuple[str, ...] = (
    'María', 'Juana', 'Rosa', 'Elena', 'Carmen', 'Silvia', 'Gladys', 'Nora',
    'Teresa', 'Lucía', 'Sonia', 'Vilma', 'Rocío', 'Marlene', 'Delia',
    'Juan', 'Carlos', 'Luis', 'Mario', 'Jorge', 'Freddy', 'Ramiro', 'Grover',
    'Wilson', 'Marcelo', 'Rubén', 'Édgar', 'Hugo', 'Iván', 'Nelson',
)
LAST_NAMES: tuple[str, ...] = (
    'Mamani', 'Quispe', 'Condori', 'Choque', 'Apaza', 'Ticona', 'Flores',
    'Chambi', 'Huanca', 'Callisaya', 'Poma', 'Colque', 'Vargas', 'Rojas',
    'Céspedes', 'Aliaga', 'Villca', 'Nina', 'Yujra', 'Cruz',
)
STORE_PREFIXES: tuple[str, ...] = (
    'Tienda', 'Mini-market', 'Abarrotes', 'Comercial', 'Market', 'Bodega',
    'Distribuidora', 'Kiosco',
)


@dataclass
class BuildConfig:
    '''Parameters of one sample-file build.'''
    source: Path = SOURCE_PATH
    output: Path = Path('tools/samples/ventas_demo.xlsx')
    rows: int = 24000
    months: int = 24
    seed: int = 20260826
    routes: tuple[int, ...] = field(default_factory = tuple)


# --- Loading and cleaning --------------------------------------------------

def load_source(path: Path) -> pd.DataFrame:
    '''
        Reads the raw distributor export and narrows it to the columns the
        sample carries.

        Args:
            path (Path): Path to the semicolon-delimited source CSV.

        Returns:
            pd.DataFrame: Frame with internal column names.

        Raises:
            FileNotFoundError: If the source file does not exist.
    '''
    if not path.exists():
        raise FileNotFoundError(f'Source dataset not found: {path}')

    # The distributor hands us the export as .xlsx; a .csv dump of the same
    # sheet is also accepted, so either artifact can seed the samples.
    if path.suffix.lower() == '.xlsx':
        frame = pd.read_excel(path)
    else:
        frame = pd.read_csv(
            path, sep = SOURCE_DELIMITER, encoding = 'utf-8-sig', low_memory = False
        )
    missing = set(SOURCE_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f'Source is missing expected columns: {sorted(missing)}')

    frame = frame[list(SOURCE_COLUMNS)].rename(columns = SOURCE_COLUMNS)
    frame['fecha'] = pd.to_datetime(frame['fecha'], dayfirst = True, errors = 'coerce')
    return frame


def clean(frame: pd.DataFrame) -> pd.DataFrame:
    '''
        Drops what would misrepresent the business: placeholder coordinates,
        zero-amount promo lines (they read as a 100% loss once a cost exists)
        and the trailing partial month.

        Args:
            frame (pd.DataFrame): Raw frame from `load_source`.

        Returns:
            pd.DataFrame: Clean frame with a 'periodo' (month) column added.
    '''
    usable_geo = (
        frame['latitud'].between(-90, 90) & frame['longitud'].between(-180, 180)
        & (frame['latitud'] != 0) & (frame['longitud'] != 0)
    )
    frame = frame[usable_geo & frame['fecha'].notna()]
    frame = frame[(frame['cantidad'] > 0) & (frame['monto'] > 0)]

    frame = frame.copy()
    frame['periodo'] = frame['fecha'].dt.to_period('M')

    # The newest month stops mid-month, which the trend chart would render as a
    # collapse in sales. Cut it rather than explain it away in every demo.
    periods = sorted(frame['periodo'].unique())
    last_day = frame.loc[frame['periodo'] == periods[-1], 'fecha'].max()
    if last_day.day < 28:
        frame = frame[frame['periodo'] != periods[-1]]

    return frame


def select_clients(frame: pd.DataFrame, config: BuildConfig) -> pd.DataFrame:
    '''
        Picks whole clients (with all their invoices) until the real months hold
        roughly the per-month volume the requested total implies.

        Sampling whole clients rather than rows is what keeps invoices intact,
        which the affinity engine needs, and keeps each client's purchase
        history continuous, which segmentation and portfolio health need.

        Args:
            frame (pd.DataFrame): Clean frame.
            config (BuildConfig): Build parameters (rows, months, seed, routes).

        Returns:
            pd.DataFrame: Frame restricted to the selected clients.
    '''
    pool = frame
    if config.routes:
        pool = pool[pool['ruta_id'].isin(config.routes)]

    real_months = pool['periodo'].nunique()
    # Every synthesized month is cloned from a real one, so the whole file lands
    # near (rows_per_real_month * months). Invert that to size the base, and
    # inflate it because the lifecycle filter removes a share of client-months.
    survival = (
        1.0 if config.months < _MIN_MONTHS_FOR_LIFECYCLES else _EXPECTED_ACTIVITY
    )
    budget = config.rows * real_months / (config.months * survival)
    base_budget = max(int(budget), real_months)

    rng = np.random.default_rng(config.seed)
    counts = pool.groupby('cliente_id').size()
    order = rng.permutation(counts.index.to_numpy())
    cumulative = counts.reindex(order).cumsum()
    keep = cumulative[cumulative <= base_budget].index

    if len(keep) == 0:
        keep = order[:1]
    return pool[pool['cliente_id'].isin(keep)].copy()


# --- Anonymization ---------------------------------------------------------

def _strip_brands(description: str) -> str:
    '''
        Removes brand tokens from a product description, preserving the generic
        descriptor that carries the analytical meaning.

        Args:
            description (str): Raw product description.

        Returns:
            str: Description without brand tokens.
    '''
    text = str(description)
    folded = unicodedata.normalize('NFKD', text.upper())
    folded = ''.join(char for char in folded if not unicodedata.combining(char))

    for token in BRAND_TOKENS:
        plain = unicodedata.normalize('NFKD', token.upper())
        plain = ''.join(char for char in plain if not unicodedata.combining(char))
        start = folded.find(plain)
        while start != -1:
            text = text[:start] + text[start + len(plain):]
            folded = folded[:start] + folded[start + len(plain):]
            start = folded.find(plain)

    return ' '.join(text.split()).strip(' -,') or 'Producto'


def anonymize(frame: pd.DataFrame, seed: int) -> pd.DataFrame:
    '''
        Replaces client, vendor and invoice identifiers with generated values
        and strips brand names from product descriptions.

        Args:
            frame (pd.DataFrame): Frame restricted to the selected clients.
            seed (int): Seed making the generated names reproducible.

        Returns:
            pd.DataFrame: Frame with no real-world identities left.
    '''
    rng = np.random.default_rng(seed)

    clients = frame['cliente_id'].unique()
    store_names = {
        client: (
            f'{rng.choice(STORE_PREFIXES)} {rng.choice(FIRST_NAMES)} '
            f'{rng.choice(LAST_NAMES)}'
        )
        for client in clients
    }
    vendors = frame['vendedor'].unique()
    vendor_names = {
        vendor: f'{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}'
        for vendor in vendors
    }
    products = frame['producto'].unique()
    product_names = {product: _strip_brands(product) for product in products}

    frame = frame.copy()
    frame['cliente'] = frame['cliente_id'].map(store_names)
    frame['vendedor'] = frame['vendedor'].map(vendor_names)
    frame['producto'] = frame['producto'].map(product_names)
    return frame


# --- Client lifecycles -----------------------------------------------------

@dataclass(frozen = True)
class ClientLifecycle:
    '''
        When a client is on the books, how often they buy and whether their
        spend is growing or fading.
    '''
    first: int                                  # first month index on the books
    last: int                                   # last month index, inclusive
    activity: float                             # chance of buying in a month
    trend: float                                # monthly multiplier on spend
    dormant: tuple[int, int] | None = None      # silent stretch, then a return

    def is_on_books(self, month: int) -> bool:
        '''
            Reports whether the client is expected to buy in a given month.

            Args:
                month (int): Month index within the generated history.

            Returns:
                bool: True when the client is active and not dormant.
        '''
        if not self.first <= month <= self.last:
            return False
        if self.dormant and self.dormant[0] <= month <= self.dormant[1]:
            return False
        return True


def _draw_lifecycle(kind: str, months: int, rng) -> ClientLifecycle:
    '''
        Builds one client's lifecycle from its behavioural class.

        Args:
            kind (str): One of the LIFECYCLE_MIX keys.
            months (int): Length of the generated history.
            rng: Seeded numpy generator.

        Returns:
            ClientLifecycle: The client's window, cadence and trend.
    '''
    activity = float(rng.uniform(*ACTIVITY_RANGE))
    trend = float(rng.uniform(*CLIENT_TREND_RANGE))
    last = months - 1

    # A short history has no room for a join, a churn and a dormant stretch
    # without emptying the file; everyone simply stays on the books.
    if months < _MIN_MONTHS_FOR_LIFECYCLES:
        return ClientLifecycle(0, last, activity, trend)

    if kind == 'nuevo':
        return ClientLifecycle(int(rng.integers(1, months - 1)), last, activity, trend)
    if kind == 'perdido':
        # Churn happens in the recent half so the loss is visible in the
        # report, without leaving a long tail of clients gone for two years.
        return ClientLifecycle(0, int(rng.integers(months // 2, months - 2)), activity, trend)
    if kind == 'recuperado':
        start = int(rng.integers(2, max(months - DORMANT_SPAN[1] - 2, 3)))
        span = int(rng.integers(*DORMANT_SPAN))
        return ClientLifecycle(0, last, activity, trend, (start, start + span))
    return ClientLifecycle(0, last, activity, trend)


def build_lifecycles(clients: np.ndarray, months: int, rng) -> dict[Any, ClientLifecycle]:
    '''
        Assigns every client a behavioural class and its resulting lifecycle.

        Args:
            clients (np.ndarray): Client identifiers.
            months (int): Length of the generated history.
            rng: Seeded numpy generator.

        Returns:
            dict: Lifecycle per client id.
    '''
    kinds = list(LIFECYCLE_MIX)
    weights = np.array([LIFECYCLE_MIX[kind] for kind in kinds])
    drawn = rng.choice(kinds, size = len(clients), p = weights / weights.sum())
    return {
        client: _draw_lifecycle(kind, months, rng)
        for client, kind in zip(clients, drawn)
    }


def _buyers_of_month(lifecycles: dict[Any, ClientLifecycle], month: int, rng,
                     draw_cadence: bool = True) -> set:
    '''
        Selects which clients order in a given month.

        `draw_cadence` is False for the real months: those already carry the
        source file's own roster, where clients naturally skip months. Drawing a
        cadence on top of it would stack two sources of absence and report a
        churn far above the 18-20% the real data actually shows.

        Args:
            lifecycles (dict): Lifecycle per client id.
            month (int): Month index within the generated history.
            rng: Seeded numpy generator.
            draw_cadence (bool): Whether to also draw the monthly purchase odds.

        Returns:
            set: Client ids buying that month.
    '''
    return {
        client for client, life in lifecycles.items()
        if life.is_on_books(month) and (not draw_cadence or rng.random() < life.activity)
    }


def _apply_client_trend(block: pd.DataFrame, lifecycles: dict[Any, ClientLifecycle],
                        month: int) -> pd.DataFrame:
    '''
        Scales each client's quantities by their own trajectory, so a declining
        client declines everywhere and shows up in the at-risk list for the
        right reason.

        Args:
            block (pd.DataFrame): Rows of one month.
            lifecycles (dict): Lifecycle per client id.
            month (int): Month index within the generated history.

        Returns:
            pd.DataFrame: The block with per-client trend applied.
    '''
    factors = block['cliente_id'].map(
        lambda client: lifecycles[client].trend ** max(month - lifecycles[client].first, 0)
    )
    block['cantidad'] = np.maximum(np.round(block['cantidad'] * factors), 1)
    return block


# --- History synthesis -----------------------------------------------------

def _source_period(target: pd.Period, real: list[pd.Period]) -> pd.Period:
    '''
        Chooses which real month a synthesized month is cloned from: the one
        with the same calendar month when it exists (so November keeps its real
        November shape), otherwise the most recent ordinary month.

        Args:
            target (pd.Period): Month being generated.
            real (list[pd.Period]): Real months available, ascending.

        Returns:
            pd.Period: The month to clone.
    '''
    for period in real:
        if period.month == target.month:
            return period
    return real[-1]


def _shift_to_period(dates: pd.Series, target: pd.Period) -> pd.Series:
    '''
        Moves dates into the target month keeping the day of month, clamped to
        the target month's length.

        Args:
            dates (pd.Series): Source datetimes.
            target (pd.Period): Destination month.

        Returns:
            pd.Series: Datetimes inside the target month.
    '''
    last_day = target.days_in_month
    days = dates.dt.day.clip(upper = last_day)
    return pd.to_datetime(
        {'year': target.year, 'month': target.month, 'day': days}
    )


def _drop_out_of_season(block: pd.DataFrame, month: int) -> pd.DataFrame:
    '''
        Removes rows of a strictly seasonal category from a month where that
        category does not sell (panetón outside Christmas, for instance).

        Args:
            block (pd.DataFrame): Rows cloned into the target month.
            month (int): Calendar month being generated (1-12).

        Returns:
            pd.DataFrame: Rows that belong in that month.
    '''
    out_of_season = block['categoria'].isin([
        category for category, months in SEASONAL_CATEGORIES.items()
        if month not in months
    ])
    return block[~out_of_season].copy()


def _scale_block(block: pd.DataFrame, factors: tuple[float, float], rng) -> pd.DataFrame:
    '''
        Applies the demand and price factors of a synthesized month.

        Args:
            block (pd.DataFrame): Rows cloned from a real month.
            factors (tuple[float, float]): (demand, price) multipliers.
            rng: Seeded numpy generator for the per-line demand noise.

        Returns:
            pd.DataFrame: Scaled rows.
    '''
    demand, price = factors
    noise = rng.normal(1.0, DEMAND_NOISE, len(block))
    block['cantidad'] = np.maximum(np.round(block['cantidad'] * demand * noise), 1)
    block['precio_unitario'] = block['precio_unitario'] * price
    return block


def extend_history(frame: pd.DataFrame, config: BuildConfig) -> pd.DataFrame:
    '''
        Extends the real months backwards into a `config.months` history by
        cloning each real month and applying trend, seasonality and noise.

        Real months are emitted untouched: they already carry their own
        seasonality, and rescaling them would count it twice.

        Args:
            frame (pd.DataFrame): Anonymized frame carrying 'precio_unitario'.
            config (BuildConfig): Build parameters (months, seed).

        Returns:
            pd.DataFrame: Frame spanning `config.months` months.
    '''
    rng = np.random.default_rng(config.seed + 1)
    real = sorted(frame['periodo'].unique())
    targets = pd.period_range(end = real[-1], periods = config.months, freq = 'M')
    lifecycles = build_lifecycles(frame['cliente_id'].unique(), config.months, rng)

    blocks: list[pd.DataFrame] = []
    for offset, target in enumerate(targets):
        age = len(targets) - 1 - offset  # months back from the newest month
        block = frame[frame['periodo'] == _source_period(target, real)].copy()
        # Membership (joins, churns, dormancy) applies to every month so the
        # movement is continuous; only the synthesized months also need a drawn
        # cadence, since they clone one real month's roster over and over.
        buyers = _buyers_of_month(lifecycles, offset, rng, draw_cadence = target not in real)
        block = block[block['cliente_id'].isin(buyers)]
        if block.empty:
            continue

        if target not in real:
            block = _drop_out_of_season(block, target.month)
            block['fecha'] = _shift_to_period(block['fecha'], target)
            block['periodo'] = target
            demand = MONTH_SEASONALITY[target.month] / (1 + MONTHLY_GROWTH) ** age
            block = _scale_block(block, (demand, 1 / (1 + MONTHLY_INFLATION) ** age), rng)

        blocks.append(_apply_client_trend(block, lifecycles, offset))

    history = pd.concat(blocks, ignore_index = True)
    return history.sort_values('fecha').reset_index(drop = True)


# --- Derived economics -----------------------------------------------------

def add_unit_economics(frame: pd.DataFrame, seed: int) -> pd.DataFrame:
    '''
        Derives the unit price from the source amount and the SYNTHETIC unit
        cost from a per-category gross margin.

        The cost is drawn once per product (not per row) so margin analysis is
        stable: a product that yields 28% must yield 28% on every invoice.

        Args:
            frame (pd.DataFrame): Frame with 'monto' and 'cantidad'.
            seed (int): Seed making the per-product margin reproducible.

        Returns:
            pd.DataFrame: Frame with 'precio_unitario' and 'costo_unitario'.
    '''
    rng = np.random.default_rng(seed + 2)
    frame = frame.copy()
    frame['precio_unitario'] = (frame['monto'] / frame['cantidad']).round(4)

    catalog = frame[['producto_id', 'categoria']].drop_duplicates('producto_id')
    jitter = rng.uniform(-MARGIN_JITTER, MARGIN_JITTER, len(catalog))
    base = catalog['categoria'].map(CATEGORY_MARGINS).fillna(DEFAULT_MARGIN)
    margins = dict(zip(catalog['producto_id'], np.clip(base + jitter, 0.05, 0.60)))

    frame['margen'] = frame['producto_id'].map(margins).fillna(DEFAULT_MARGIN)
    frame['costo_unitario'] = (frame['precio_unitario'] * (1 - frame['margen'])).round(4)
    return frame


def to_template(frame: pd.DataFrame) -> pd.DataFrame:
    '''
        Renumbers invoices per month and projects the frame onto the friendly
        template headers served by INGEST.

        Args:
            frame (pd.DataFrame): Fully built frame.

        Returns:
            pd.DataFrame: Frame ready to be written as the 'Ventas' sheet.
    '''
    frame = frame.copy()
    # An invoice number must stay unique after a month is cloned, and must not
    # leak the distributor's real numbering.
    keys = frame['periodo'].astype(str) + '|' + frame['factura'].astype(str)
    codes = pd.factorize(keys)[0] + 1
    frame['factura'] = [f'F-{code:06d}' for code in codes]

    frame['monto_total'] = (frame['cantidad'] * frame['precio_unitario']).round(2)
    frame['precio_unitario'] = frame['precio_unitario'].round(2)
    frame['costo_unitario'] = frame['costo_unitario'].round(2)
    frame['fecha'] = frame['fecha'].dt.date

    return frame[list(TEMPLATE_HEADERS)].rename(columns = TEMPLATE_HEADERS)


def build_provenance_sheet(frame: pd.DataFrame) -> pd.DataFrame:
    '''
        Builds the sheet that states which fields are real and which are
        synthetic, so the file can be handed to a prospect without implying
        that the margin figures came from a real ledger.

        Args:
            frame (pd.DataFrame): The template-shaped frame.

        Returns:
            pd.DataFrame: Two-column provenance table.
    '''
    start, end = frame['Fecha'].min(), frame['Fecha'].max()
    notes = [
        ('Propósito', 'Archivo de ejemplo de SmartDecisions. Muestra el formato '
                      'de datos que necesitamos de tu operación.'),
        ('Período', f'{start} a {end}'),
        ('Filas', f'{len(frame):,}'.replace(',', '.')),
        ('Cantidad, Precio Unitario', 'Derivados de una operación real de '
                                      'distribución de consumo masivo.'),
        ('Costo Unitario', 'SIMULADO a partir de un margen bruto típico por '
                           'categoría. No proviene de una contabilidad real.'),
        ('Historial anterior al período real', 'SIMULADO: se proyectó hacia '
                                               'atrás con tendencia, '
                                               'estacionalidad y ruido.'),
        ('Movimiento de clientes', 'SIMULADO: altas, bajas, clientes que dejan '
                                   'de comprar y vuelven, y una tendencia propia '
                                   'por cliente. Calibrado contra la rotación '
                                   'real del archivo de origen (18-20% mensual).'),
        ('Cliente, Vendedor, Nro Factura', 'Anonimizados. Cualquier parecido '
                                           'con un nombre real es casual.'),
        ('Producto', 'Descripción genérica; se retiraron las marcas.'),
        ('Latitud, Longitud', 'Reales. Habilitan el módulo de rutas.'),
    ]
    return pd.DataFrame(notes, columns = ['Campo', 'Origen'])


def build(config: BuildConfig) -> pd.DataFrame:
    '''
        Runs the whole pipeline and writes the workbook.

        Args:
            config (BuildConfig): Build parameters.

        Returns:
            pd.DataFrame: The template-shaped frame that was written.
    '''
    frame = select_clients(clean(load_source(config.source)), config)
    frame = add_unit_economics(anonymize(frame, config.seed), config.seed)
    frame = extend_history(frame, config)
    sheet = to_template(frame)

    config.output.parent.mkdir(parents = True, exist_ok = True)
    with pd.ExcelWriter(config.output, engine = 'openpyxl') as writer:
        sheet.to_excel(writer, sheet_name = 'Ventas', index = False)
        build_provenance_sheet(sheet).to_excel(
            writer, sheet_name = 'Origen de los datos', index = False
        )
    return sheet


def describe(sheet: pd.DataFrame, output: Path) -> None:
    '''
        Prints the diagnostics that decide whether a sample is dense enough for
        every module to have signal.

        Args:
            sheet (pd.DataFrame): The generated template-shaped frame.
            output (Path): Where the workbook was written.

        Returns:
            None
    '''
    dates = pd.to_datetime(sheet['Fecha'])
    invoices = sheet['Nro Factura'].nunique()
    margin = 1 - (sheet['Costo Unitario'] / sheet['Precio Unitario']).mean()

    print(f'\n{output}')
    print(f'  filas            {len(sheet):,}')
    print(f'  período          {dates.min().date()} → {dates.max().date()} '
          f'({dates.dt.to_period("M").nunique()} meses)')
    print(f'  facturas         {invoices:,}  ({len(sheet) / invoices:.2f} líneas/factura)')
    print(f'  clientes         {sheet["Cliente"].nunique():,}')
    print(f'  productos        {sheet["Producto"].nunique():,} '
          f'en {sheet["Categoria"].nunique()} categorías')
    print(f'  vendedores       {sheet["Vendedor"].nunique()}')
    print(f'  venta total      Bs {sheet["Monto Total"].sum():,.0f}')
    print(f'  margen bruto     {margin * 100:.1f}%')
    print(f'  geo completa     {sheet["Latitud"].notna().mean() * 100:.0f}%')


def parse_args() -> BuildConfig:
    '''
        Parses the command line into a BuildConfig.

        Returns:
            BuildConfig: Parameters for a single build.
    '''
    parser = argparse.ArgumentParser(description = 'Build a SmartDecisions sample dataset.')
    parser.add_argument('--source', type = Path, default = SOURCE_PATH)
    parser.add_argument('--output', type = Path, default = Path('tools/samples/ventas_demo.xlsx'))
    parser.add_argument('--rows', type = int, default = 24000)
    parser.add_argument('--months', type = int, default = 24)
    parser.add_argument('--seed', type = int, default = 20260826)
    parser.add_argument('--routes', type = int, nargs = '*', default = [])
    args = parser.parse_args()

    return BuildConfig(
        source = args.source, output = args.output, rows = args.rows,
        months = args.months, seed = args.seed, routes = tuple(args.routes)
    )


if __name__ == '__main__':
    CONFIG = parse_args()
    describe(build(CONFIG), CONFIG.output)
