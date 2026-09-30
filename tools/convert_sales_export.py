'''
    Turns a client's raw ERP sales export into the template the product reads.

    A client does not fill in our template by hand: they already have a report
    their system prints every month, and asking them to retype 5.000 rows is
    how a pilot dies. So the conversion is OUR job, not theirs — this script is
    what we run over the file they send.

    Two things it must not get wrong:

    1. **The output is the contract, not an approximation.** The headers and
       their order come from `TEMPLATE_COLUMNS` in `schemas/ingest.py`, the
       same tuple the validator reads. A mapping written by hand diverges the
       day a column is added.
    2. **Simulated coordinates are declared as simulated.** This export has no
       latitude or longitude, and Routes needs them to show anything. They are
       generated deterministically from the delivery point so the same shop
       lands on the same corner every run — but they are invented, and a demo
       that forgets that is a demo that lies.

    Usage:
        python -m tools.convert_sales_export "base 2025.xlsx"
        python -m tools.convert_sales_export "base 2025.xlsx" --out /tmp/ventas.xlsx
'''
import argparse
import hashlib
import sys
from pathlib import Path
from typing import Dict, Optional

import pandas as pd


# The microservice declares the contract; this script imports it instead of
# repeating it.
INGEST_PATH = Path(__file__).resolve().parent.parent / 'services' / 'ingest'
sys.path.insert(0, str(INGEST_PATH))

# pylint: disable=wrong-import-position
from schemas.ingest import TEMPLATE_HEADERS  # noqa: E402

# Where the report's own header row sits. The first rows carry the title and
# the period, which is what every ERP print-out puts above the data.
HEADER_ROW = 5

# Source column for each template header. Everything absent from this map is
# left empty: the contract marks it optional, and inventing a value would put
# data in the client's mouth.
COLUMN_SOURCES: Dict[str, str] = {
    'Fecha': 'Fecha',
    'Nro Factura': 'Nro_Trans',
    'Cliente': 'Cliente',
    'Vendedor': 'Preventista',
    'Producto': 'Descripcion',
    'Categoria': 'Linea',
    'Cantidad': 'Cantidad',
    'Precio Unitario': 'PUnit',
    'Costo Unitario': 'CostoUnit',
    'Monto Total': 'Total',
}

# The export's single `Canal_Dist` says SUCURSALES for every row, which
# separates nothing. The price list is the real segmentation: it is the one
# the commercial team already uses to decide what each client pays.
CHANNEL_FROM_LIST = (
    ('DISTRIBUIDOR', 'Distribuidor'),
    ('MAYORISTA', 'Mayorista'),
    ('SUPERMERCADO', 'Supermercado'),
    ('INSTITUCIONAL', 'Institucional'),
    ('MINORISTA', 'Minorista'),
)
DEFAULT_CHANNEL = 'General'

# The price lists all end in LPZ, so the operation is La Paz. The simulated
# clients are scattered over the city and El Alto, each zone a real one with
# its approximate centre, so the map looks like the city it claims to be.
#
# A chain's branches share one ERP code and differ only by name — HIPERMAXI
# MIRAFLORES and HIPERMAXI SATELITE are both client 375 — so the point is
# drawn per DELIVERY POINT, never per code: four branches on one corner would
# make every route this demo shows a lie. When the name says where it is, it
# is taken at its word.
CITY = 'La Paz'
REGION = 'Occidente'
SIMULATED_ZONES = (
    ('Centro', -16.4960, -68.1336),
    ('Sopocachi', -16.5140, -68.1300),
    ('Miraflores', -16.4990, -68.1180),
    ('San Pedro', -16.5060, -68.1420),
    ('Zona Sur', -16.5435, -68.0713),
    ('Villa Fátima', -16.4780, -68.1160),
    ('Max Paredes', -16.4900, -68.1500),
    ('El Alto Sur', -16.5100, -68.1900),
)
# How far a client may fall from the centre of its zone, in degrees. About
# 1,7 km, which keeps a zone looking like a neighbourhood and not a province.
ZONE_SPREAD = 0.015

# Neighbourhoods a paceño names without naming its zone. Matching only the
# eight zone labels above would scatter ACHUMANI and CALACOTO across the map,
# and the first person to look at the demo lives here.
ZONE_ALIASES = (
    ('ACHUMANI', 'Zona Sur'), ('CALACOTO', 'Zona Sur'), ('IRPAVI', 'Zona Sur'),
    ('OBRAJES', 'Zona Sur'), ('COTA COTA', 'Zona Sur'), ('SAN MIGUEL', 'Zona Sur'),
    ('RIO SECO', 'El Alto Sur'), ('SATELITE', 'El Alto Sur'),
    ('SATÉLITE', 'El Alto Sur'), ('EL ALTO', 'El Alto Sur'),
    ('SAN PEDRO', 'San Pedro'), ('GARITA', 'Max Paredes'),
    ('VILLA FATIMA', 'Villa Fátima'), ('OBELISCO', 'Centro'),
    ('PRADO', 'Centro'), ('ESTACION CENTRAL', 'Centro')
)

# A sale settled in cash against one settled on credit. The export reports
# both amounts per row; whichever carries the money is the condition.
CASH_TERMS = 'CONTADO'
CREDIT_TERMS = 'CREDITO'


def _stable_fraction(
    seed: str,
    salt: str
) -> float:
    '''
        A number in [-1, 1) that is always the same for the same client.

        Deterministic on purpose: a client that jumps to another corner every
        time the file is converted makes the route history meaningless.

        Args:
            seed (str): The delivery point's name.
            salt (str): Distinguishes latitude from longitude.

        Returns:
            float: The fraction.
    '''
    digest = hashlib.sha256(f'{seed}|{salt}'.encode('utf-8')).digest()
    return int.from_bytes(digest[:4], 'big') / 0x7FFFFFFF - 1.0


def _zone_of(name: str) -> tuple:
    '''
        The zone a delivery point belongs to.

        Args:
            name (str): The client name as the export writes it.

        Returns:
            tuple: Zone name and the coordinates of its centre.
    '''
    centres = {zone[0]: zone for zone in SIMULATED_ZONES}
    upper = name.upper()
    for label, zone in ZONE_ALIASES:
        if label in upper:
            return centres[zone]
    for zone in SIMULATED_ZONES:
        if zone[0].upper() in upper:
            return zone
    return SIMULATED_ZONES[
        int(hashlib.sha256(name.encode('utf-8')).hexdigest(), 16) % len(SIMULATED_ZONES)
    ]


def _simulated_places(names: pd.Series) -> pd.DataFrame:
    '''
        Invents a zone and a point for every delivery point in the export.

        Args:
            names (pd.Series): The distinct client names.

        Returns:
            pd.DataFrame: Indexed by client name, with zone, latitude and
                longitude.
    '''
    rows = []
    for name in names:
        key = str(name)
        zone, centre_lat, centre_lon = _zone_of(key)
        rows.append({
            'name': key,
            'Zona': zone,
            'Latitud': round(centre_lat + _stable_fraction(key, 'lat') * ZONE_SPREAD, 6),
            'Longitud': round(centre_lon + _stable_fraction(key, 'lon') * ZONE_SPREAD, 6)
        })
    return pd.DataFrame(rows).set_index('name')


def _channel_of(price_list: object) -> str:
    '''
        The commercial channel a price list implies.

        Args:
            price_list (object): Value of the `Lista` column.

        Returns:
            str: The channel.
    '''
    text = str(price_list).upper()
    for marker, channel in CHANNEL_FROM_LIST:
        if marker in text:
            return channel
    return DEFAULT_CHANNEL


def _payment_terms(row: pd.Series) -> str:
    '''
        Whether the row was settled in cash or on credit.

        Args:
            row (pd.Series): One line of the export.

        Returns:
            str: One of the two values the contract allows.
    '''
    return CREDIT_TERMS if float(row.get('Credito') or 0) > 0 else CASH_TERMS


def convert(source: Path) -> pd.DataFrame:
    '''
        Reads the ERP export and returns it shaped as the sales template.

        Args:
            source (Path): The workbook the client sent.

        Returns:
            pd.DataFrame: One row per sale line, columns in contract order.

        Raises:
            ValueError: If the export has no data rows under its header.
    '''
    raw = pd.read_excel(source, sheet_name = 0, header = HEADER_ROW)
    raw = raw.dropna(subset = ['Nro_Trans', 'Fecha'])
    if raw.empty:
        raise ValueError(f'{source} has no rows under its header.')

    places = _simulated_places(raw['Cliente'].astype(str).unique())

    converted = pd.DataFrame(index = raw.index)
    for header in TEMPLATE_HEADERS:
        origin = COLUMN_SOURCES.get(header)
        converted[header] = raw[origin] if origin else None

    points = raw['Cliente'].astype(str)
    converted['Ciudad'] = CITY
    converted['Region'] = REGION
    converted['Zona'] = points.map(places['Zona']).values
    converted['Latitud'] = points.map(places['Latitud']).values
    converted['Longitud'] = points.map(places['Longitud']).values
    converted['Canal'] = raw['Lista'].map(_channel_of)
    converted['Condicion Venta'] = raw.apply(_payment_terms, axis = 1)
    converted['Fecha'] = pd.to_datetime(converted['Fecha']).dt.date
    return converted[list(TEMPLATE_HEADERS)]


def _report(
    converted: pd.DataFrame,
    destination: Path
) -> None:
    '''
        Prints what was produced, so the conversion can be checked.

        Args:
            converted (pd.DataFrame): The result.
            destination (Path): Where it was written.
    '''
    filled = [header for header in TEMPLATE_HEADERS if converted[header].notna().any()]
    empty = [header for header in TEMPLATE_HEADERS if header not in filled]
    print(f'{len(converted)} rows -> {destination}')
    print(f'  clients  {converted["Cliente"].nunique()}')
    print(f'  products {converted["Producto"].nunique()}')
    print(f'  period   {converted["Fecha"].min()} .. {converted["Fecha"].max()}')
    print(f'  channels {sorted(converted["Canal"].unique())}')
    print(f'  filled   {filled}')
    print(f'  empty    {empty or "none"}')
    print('  NOTE: Zona, Latitud and Longitud are SIMULATED — the export has none.')


def main(argument_list: Optional[list] = None) -> int:
    '''
        Entry point.

        Args:
            argument_list (list): Arguments, for tests. Defaults to argv.

        Returns:
            int: Process exit code.
    '''
    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument('source', help = 'The ERP export the client sent.')
    parser.add_argument('--out', default = None,
                        help = 'Where to write. Defaults to the source name with _ventas.')
    arguments = parser.parse_args(argument_list)

    source = Path(arguments.source)
    destination = Path(arguments.out) if arguments.out else \
        source.with_name(f'{source.stem}_ventas.xlsx')

    converted = convert(source)
    converted.to_excel(destination, index = False, sheet_name = 'Datos')
    _report(converted, destination)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
