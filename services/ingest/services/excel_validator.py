'''
    DataFrame-level validation for the sales Excel template (v1).

    The contract follows SMARTDECISIONS.md §5: one row per sales line. Required
    columns let the analytics engine (paso 3 of the POC) compute affinity rules
    and drop-size weighting. Optional columns enrich the UI and zone analysis.

    Validation is done with pandera's pandas-flavored DataFrameSchema. Error
    messages are returned in Spanish because the end user is non-technical
    (per SMARTDECISIONS.md §10).
'''
from typing import Final
import pandas as pd
import pandera.pandas as pa
from pandera.errors import SchemaErrors

from services.logger_config import custom_logger as logger


TEMPLATE_VERSION: Final[str] = 'v2'

REQUIRED_COLUMNS: Final[list[str]] = [
    'id_pedido',
    'fecha',
    'id_punto_venta',
    'id_producto',
    'cantidad',
]

OPTIONAL_COLUMNS: Final[list[str]] = [
    'nombre_pdv',
    'zona',
    'nombre_producto',
    'precio_unitario',
    'monto_total',
    # Unlocks gross-margin KPIs; absent in most ERP exports, hence optional.
    'costo_unitario',
    # v2 enriching columns: power the commercial dashboard and route module.
    'categoria',
    'canal',
    'region',
    'ciudad',
    'vendedor',
    'latitud',
    'longitud',
]


SCHEMA: Final[pa.DataFrameSchema] = pa.DataFrameSchema(
    columns = {
        'id_pedido': pa.Column(
            dtype = 'object',
            nullable = False,
            coerce = True,
            checks = pa.Check.str_length(min_value = 1, max_value = 64),
            description = 'Identificador de pedido (agrupa productos de una misma venta).'
        ),
        'fecha': pa.Column(
            dtype = 'datetime64[ns]',
            nullable = False,
            coerce = True,
            description = 'Fecha de la venta (ISO o dd/mm/aaaa).'
        ),
        'id_punto_venta': pa.Column(
            dtype = 'object',
            nullable = False,
            coerce = True,
            checks = pa.Check.str_length(min_value = 1, max_value = 64),
            description = 'Identificador del punto de venta / cliente.'
        ),
        'nombre_pdv': pa.Column(
            dtype = 'object',
            nullable = True,
            required = False,
            coerce = True,
            description = 'Nombre legible del punto de venta (solo para UI).'
        ),
        'zona': pa.Column(
            dtype = 'object',
            nullable = True,
            required = False,
            coerce = True,
            description = 'Zona geográfica del PdV para análisis de rutas.'
        ),
        'id_producto': pa.Column(
            dtype = 'object',
            nullable = False,
            coerce = True,
            checks = pa.Check.str_length(min_value = 1, max_value = 64),
            description = 'SKU del producto vendido.'
        ),
        'nombre_producto': pa.Column(
            dtype = 'object',
            nullable = True,
            required = False,
            coerce = True,
            description = 'Nombre legible del producto (solo para UI).'
        ),
        'cantidad': pa.Column(
            dtype = 'float64',
            nullable = False,
            coerce = True,
            checks = pa.Check.greater_than(0),
            description = 'Unidades vendidas (> 0).'
        ),
        'precio_unitario': pa.Column(
            dtype = 'float64',
            nullable = True,
            required = False,
            coerce = True,
            checks = pa.Check.greater_than_or_equal_to(0),
            description = 'Precio unitario (necesario para Drop Size en moneda).'
        ),
        'monto_total': pa.Column(
            dtype = 'float64',
            nullable = True,
            required = False,
            coerce = True,
            checks = pa.Check.greater_than_or_equal_to(0),
            description = (
                'Monto total de la línea '
                '(si falta, se calcula cantidad * precio_unitario).'
            )
        ),
        'costo_unitario': pa.Column(
            dtype = 'float64',
            nullable = True,
            required = False,
            coerce = True,
            checks = pa.Check.greater_than_or_equal_to(0),
            description = (
                'Costo unitario del producto '
                '(habilita margen bruto por producto, cliente y vendedor).'
            )
        ),
        # --- v2 enriching columns (optional): commercial dashboard + routes ---
        'categoria': pa.Column(
            dtype = 'object', nullable = True, required = False, coerce = True,
            description = 'Categoría / línea del producto (para análisis por rubro).'
        ),
        'canal': pa.Column(
            dtype = 'object', nullable = True, required = False, coerce = True,
            description = 'Canal comercial (mayorista, detalle, HORECA, etc.).'
        ),
        'region': pa.Column(
            dtype = 'object', nullable = True, required = False, coerce = True,
            description = 'Región o departamento del punto de venta.'
        ),
        'ciudad': pa.Column(
            dtype = 'object', nullable = True, required = False, coerce = True,
            description = 'Ciudad del punto de venta.'
        ),
        'vendedor': pa.Column(
            dtype = 'object', nullable = True, required = False, coerce = True,
            description = 'Vendedor / preventista responsable de la venta.'
        ),
        'latitud': pa.Column(
            dtype = 'float64', nullable = True, required = False, coerce = True,
            checks = pa.Check.in_range(-90, 90),
            description = 'Latitud del punto de venta (para optimización de rutas).'
        ),
        'longitud': pa.Column(
            dtype = 'float64', nullable = True, required = False, coerce = True,
            checks = pa.Check.in_range(-180, 180),
            description = 'Longitud del punto de venta (para optimización de rutas).'
        ),
    },
    strict = 'filter',
    coerce = True,
    ordered = False,
    description = (
        f'SmartDecisions sales template {TEMPLATE_VERSION}. Required columns: '
        f'{", ".join(REQUIRED_COLUMNS)}. Optional columns: {", ".join(OPTIONAL_COLUMNS)}.'
    )
)


_RULE_PREFIX_MESSAGES_ES: Final[list[tuple[str, str]]] = [
    ('not_nullable', 'Este campo es obligatorio y no puede estar vacío.'),
    ('coerce_dtype', 'El valor no tiene el tipo de dato esperado para esta columna.'),
    ('dtype', 'El valor no tiene el tipo de dato esperado para esta columna.'),
    ('str_length', 'El texto debe tener entre 1 y 64 caracteres.'),
    ('greater_than_or_equal_to', 'El valor debe ser mayor o igual al mínimo permitido.'),
    ('greater_than', 'El valor debe ser mayor que el mínimo permitido.'),
    ('column_in_schema', 'Esta columna no forma parte de la plantilla esperada.'),
    ('column_in_dataframe', 'Falta esta columna obligatoria en el archivo.'),
]


def _translate_rule(check_name: str | None) -> str:
    '''
        Maps pandera check names (including parameterized ones like
        "greater_than(0)" or "coerce_dtype('datetime64[ns]')") to user-facing
        Spanish messages via prefix matching.

        Args:
            check_name (str | None): Pandera check identifier.

        Returns:
            str: Localized message suitable for non-technical end users.
    '''
    if not check_name:
        return 'Valor inválido para esta columna.'
    for prefix, message in _RULE_PREFIX_MESSAGES_ES:
        if check_name.startswith(prefix):
            return message
    return f'Regla no cumplida: {check_name}.'


def validate(dataframe: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    '''
        Validates a sales DataFrame against the v1 template contract.

        Lazy mode: collects all errors instead of failing on the first.

        Args:
            dataframe (pd.DataFrame): Raw DataFrame parsed from the user's Excel.

        Returns:
            tuple[pd.DataFrame, list[dict]]:
                - The coerced DataFrame (or the original on full failure).
                - A list of structured errors. Each item has keys: row, column,
                  value, rule, message. Empty if the file is valid.
    '''
    errors: list[dict] = []

    if dataframe.empty:
        errors.append({
            'row': 0,
            'column': '(archivo)',
            'value': None,
            'rule': 'empty_file',
            'message': 'El archivo no contiene filas de datos.'
        })
        return dataframe, errors

    try:
        validated = SCHEMA.validate(dataframe, lazy = True)
        return validated, []
    except SchemaErrors as schema_errors:
        failure_cases = schema_errors.failure_cases
        for _, failure in failure_cases.iterrows():
            row_idx = failure.get('index')
            row_number = int(row_idx) + 2 if pd.notna(row_idx) else 0
            check_name = failure.get('check') or 'unknown'
            raw_failure_value = failure.get('failure_case')
            # Schema-level checks (e.g. missing/extra column) carry the
            # offending column name in `failure_case`, not in `column`.
            if check_name in ('column_in_dataframe', 'column_in_schema'):
                column_name = str(raw_failure_value)
                value_repr = None
            else:
                column_name = str(failure.get('column') or '(global)')
                value_repr = None if pd.isna(raw_failure_value) else str(raw_failure_value)
            errors.append({
                'row': row_number,
                'column': column_name,
                'value': value_repr,
                'rule': str(check_name),
                'message': _translate_rule(check_name)
            })

        message = (
            f'Excel validation found {len(errors)} issue(s) across '
            f'{failure_cases["column"].nunique()} column(s).'
        )
        logger.info(message)
        return dataframe, errors
