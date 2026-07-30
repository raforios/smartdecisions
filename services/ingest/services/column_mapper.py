'''
    Column mapping layer for the sales ingest pipeline.

    Real-world sales exports never use the canonical template headers verbatim
    (e.g. a distributor's file calls the invoice 'Numero Factura', the SKU
    'Codigo Sap', the client 'Cliente ID'). This module normalizes any incoming
    header and maps it to the canonical name the validator expects, so the same
    engine ingests both the SmartDecisions template and a raw ERP export.

    The mapping is intentionally alias-based (not positional) and accent/-case
    insensitive. Unknown columns are left untouched; the validator's
    `strict='filter'` then drops whatever is not part of the contract.
'''
import re
import unicodedata
from typing import Final

import pandas as pd


# Canonical column -> set of accepted source aliases (already normalized:
# lowercase, no accents, collapsed spaces). The canonical name itself is always
# accepted implicitly.
COLUMN_ALIASES: Final[dict[str, set[str]]] = {
    'id_pedido': {
        'id pedido', 'pedido', 'numero factura', 'nro factura', 'factura',
        'id venta', 'transaccion', 'ticket', 'orden', 'id orden'
    },
    'fecha': {'fecha', 'fecha venta', 'date', 'dia'},
    'id_punto_venta': {
        'id punto venta', 'punto de venta', 'pdv', 'cliente id', 'id cliente',
        'codigo cliente', 'cod cliente'
    },
    'nombre_pdv': {
        'nombre pdv', 'nombre punto venta', 'cliente', 'nombre cliente',
        'razon social'
    },
    'zona': {'zona', 'barrio', 'sector'},
    'id_producto': {
        'id producto', 'codigo sap', 'cod sap', 'sku', 'codigo producto',
        'cod producto', 'codigo', 'codigo nestle'
    },
    'nombre_producto': {'nombre producto', 'producto', 'descripcion', 'articulo'},
    'cantidad': {'cantidad', 'unidades', 'qty', 'cant', 'volumen'},
    'precio_unitario': {'precio unitario', 'precio', 'precio unit', 'pu'},
    'monto_total': {
        'monto total', 'monto final', 'monto', 'importe', 'total', 'venta',
        'valor'
    },
    # --- v2 enriching columns (all optional) ---
    'categoria': {'categoria', 'category', 'linea', 'familia', 'rubro'},
    'canal': {'canal', 'channel'},
    'region': {'region', 'departamento', 'depto'},
    'ciudad': {'ciudad', 'city', 'localidad'},
    'vendedor': {'vendedor', 'seller', 'ejecutivo', 'preventista', 'usuario vendedor'},
    'latitud': {'latitud', 'lat', 'latitude'},
    'longitud': {'longitud', 'lng', 'lon', 'long', 'longitude'},
}


def _normalize(header: object) -> str:
    '''
        Lowercases, strips accents and asterisks, and collapses whitespace so a
        header matches its alias regardless of formatting (e.g. 'Código SAP *'
        -> 'codigo sap').
    '''
    text = unicodedata.normalize('NFKD', str(header))
    text = ''.join(char for char in text if not unicodedata.combining(char))
    text = text.lower().replace('*', ' ')
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', text)).strip()


def _build_lookup() -> dict[str, str]:
    '''
        Builds a flat {normalized_alias: canonical_name} lookup, including each
        canonical name as its own alias.
    '''
    lookup: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        lookup[_normalize(canonical)] = canonical
        for alias in aliases:
            lookup[alias] = canonical
    return lookup


_LOOKUP: Final[dict[str, str]] = _build_lookup()


def map_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    '''
        Renames the DataFrame's columns to the canonical template names using
        the alias lookup. Columns with no known alias are left as-is (the
        validator drops them). If two source columns map to the same canonical
        name, the first occurrence wins and the rest keep their original name.

        Args:
            dataframe (pd.DataFrame): Raw DataFrame parsed from the user's file.

        Returns:
            pd.DataFrame: The same frame with recognized columns renamed.
    '''
    rename_map: dict[object, str] = {}
    already_taken: set[str] = set()
    for original in dataframe.columns:
        canonical = _LOOKUP.get(_normalize(original))
        if canonical and canonical not in already_taken:
            rename_map[original] = canonical
            already_taken.add(canonical)
    return dataframe.rename(columns = rename_map)
