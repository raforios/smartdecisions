'''
    Optimization controllers.

    Orchestration adapted from the legacy monolith
    (`api/controllers/optimization.py`). The math is unchanged; the only
    structural change is the data source: the monolith ran a raw SQL query
    against Postgres (`SELECT * FROM routes WHERE route_id = X AND day = Y`),
    while this microservice reads the same shape from DynamoDB via
    `services.route_data.get_route_points`.
'''
import csv
import io
from typing import List, Optional, Tuple
import pandas as pd
from boto3.resources.base import ServiceResource

from schemas.optimization import (
    BulkUploadResponse,
    DataMapResponse,
    OptimizationResponse,
    RouteResponse
)
from services.events_emitter import audit_event
from services.exceptions import InvalidInputError
from services.ml_optimization import (
    GeoAnalyzer,
    distance_between_points,
    fiter_order_df,
    optimal_route
)
from services.route_data import bulk_upload_points, get_route_points
from services.routing import road_segment


# ---------------------------------------------------------------------------
# Data-source adapter
# ---------------------------------------------------------------------------
def _route_points_to_df(items: List[dict]) -> pd.DataFrame:
    '''
        Converts the Dynamo response (RoutePoint items) into the DataFrame
        shape the algorithm expects: columns day, client_id, y (lat), x (lon).
    '''
    df = pd.DataFrame(items)
    df = df[['day', 'client_id', 'latitude', 'longitude']].reset_index(drop = True)
    df = df.rename(columns = {'latitude': 'y', 'longitude': 'x'})
    # Dynamo returns numeric values as Decimal — cast to native types so the
    # algorithm doesn't propagate Decimal-vs-float comparisons.
    df['day'] = df['day'].astype(int)
    df['client_id'] = df['client_id'].astype(int)
    df['y'] = df['y'].astype(float)
    df['x'] = df['x'].astype(float)
    return df


def _load_dataframe(
    dynamodb_resource: ServiceResource,
    route_id: int,
    day: int
) -> pd.DataFrame:
    '''
        Reads the route points from DynamoDB and returns them as the dataframe
        the optimization algorithm consumes. Replaces the monolith's
        `database_to_df` (SQL).
    '''
    items = get_route_points(
        dynamodb_resource = dynamodb_resource,
        route_id = route_id,
        day = day
    )
    return _route_points_to_df(items)


# ---------------------------------------------------------------------------
# Algorithm helpers (verbatim from monolith)
# ---------------------------------------------------------------------------
def _draw_map(dtf: pd.DataFrame) -> pd.DataFrame:
    '''
        Tags the first / last / middle points with their map color.
    '''
    data = dtf.copy()
    size, _ = data.shape
    data_order = data.sort_values(by = 'client_id', ascending = True)
    data = data_order.reset_index(drop = True)
    data.loc[0, 'color'] = 'red'
    mask = (data.index >= 1) & (data.index < len(data) - 1)
    data.loc[mask, 'color'] = 'black'
    data.loc[size - 1, 'color'] = 'green'
    return data


def _distances(dtf: pd.DataFrame) -> pd.DataFrame:
    '''
        Creates the dataframe with linear distance calculations.
    '''
    dtf_distances = pd.DataFrame({
        'origin': dtf.at[0, 'client_id'],
        'target': dtf.at[0, 'client_id'],
        'x': dtf.at[0, 'x'],
        'y': dtf.at[0, 'y'],
        'distance': 0
    }, index = [0])
    for i in range(len(dtf)):
        for j in range(i + 1, len(dtf)):
            node_1 = (dtf.at[i, 'x'], dtf.at[i, 'y'])
            node_2 = (dtf.at[j, 'x'], dtf.at[j, 'y'])
            distance = distance_between_points(node_1, node_2)
            new_row = pd.DataFrame({
                'origin': dtf.at[i, 'client_id'],
                'target': dtf.at[j, 'client_id'],
                'x': dtf.at[j, 'x'],
                'y': dtf.at[j, 'y'],
                'distance': distance
            }, index = [i * j])
            dtf_distances = pd.concat([dtf_distances, new_row], ignore_index = True)
    return dtf_distances.reset_index(drop = True)


def _final_data(dtf: pd.DataFrame, dtf_distances: pd.DataFrame) -> pd.DataFrame:
    '''
        Creates the dataframe with the optimized and organized route.
    '''
    dtf_final = pd.DataFrame({
        'origin': dtf.at[0, 'target'],
        'target': dtf.at[1, 'target'],
        'distance': dtf.at[1, 'distance'],
        'x': dtf.at[0, 'x'],
        'y': dtf.at[0, 'y']
    }, index = [0])

    origin = dtf.at[0, 'target']
    target = dtf.at[1, 'target']
    dtf_final = optimal_route(len(dtf), origin, target, dtf_distances, dtf_final)

    dtf_final = pd.merge(
        dtf_final, dtf, left_on = 'origin', right_on = 'target', how = 'left'
    )
    dtf_final.drop(
        columns = ['x_x', 'y_x', 'origin_y', 'target_y', 'distance_y'],
        axis = 1, inplace = True
    )
    dtf_final = dtf_final.rename(columns = {
        'origin_x': 'origin', 'distance_x': 'distance',
        'y_y': 'y', 'x_y': 'x', 'target_x': 'target'
    })
    return dtf_final


def _final_route(dtf: pd.DataFrame) -> pd.DataFrame:
    '''
        Projects the ordered route onto the real road network via OSRM and
        returns it with per-segment linear time, real road distance/duration
        and the street geometry (list of [longitude, latitude] points).
    '''
    df_route = dtf.copy()
    df_route.index.name = 'visit_order'
    df_route.drop(columns = ['target'], axis = 1, inplace = True)

    df_route_segments = df_route.join(
        df_route.shift(-1),
        rsuffix = '_next'
    ).dropna()
    df_route_segments.drop(columns = ['distance_next'], axis = 1, inplace = True)
    df_route_segments = df_route_segments.rename(columns = {'origin_next': 'target'})

    df_route_segments['time_seg'] = df_route_segments.apply(
        lambda stop: distance_between_points(
            (stop.y, stop.x), (stop.y_next, stop.x_next)
        ),
        axis = 1
    )

    # Each segment is resolved against the OSRM road network (see services.routing).
    segments = df_route_segments.apply(
        lambda stop: road_segment((stop.y, stop.x), (stop.y_next, stop.x_next)),
        axis = 1
    )
    df_route_segments['road_distance'] = segments.apply(lambda leg: leg['distance'])
    df_route_segments['road_duration'] = segments.apply(lambda leg: leg['duration'])
    df_route_segments['route'] = segments.apply(lambda leg: leg['geometry'])
    return df_route_segments


def _df_to_pydantic(df: pd.DataFrame, model) -> list:
    '''
        Transforms a dataframe into a list of Pydantic instances.
    '''
    data = df.to_dict(orient = 'records')
    return [model(**item) for item in data]


# ---------------------------------------------------------------------------
# Public controllers (mirror monolith signatures)
# ---------------------------------------------------------------------------
async def preparing_data_controller(
    dynamodb_resource: ServiceResource,
    route_id: int,
    day: int
) -> Optional[List[DataMapResponse]]:
    '''
        Returns the base map data (geolocated client points tagged with color).
    '''
    dtf = _load_dataframe(dynamodb_resource, route_id, day)
    data = _draw_map(dtf)
    return _df_to_pydantic(data, DataMapResponse)


async def data_ordered_controller(
    dynamodb_resource: ServiceResource,
    route_id: int,
    day: int
) -> Optional[List[OptimizationResponse]]:
    '''
        Returns the ordered linear-distance pairs (origin → target).
    '''
    dtf = _load_dataframe(dynamodb_resource, route_id, day)
    dtf_distances = _distances(dtf)
    dtf_order = fiter_order_df(
        dtf_distances['origin'] == int(dtf_distances['origin'].iloc[0]),
        'distance',
        dtf_distances
    )
    dtf_final = _final_data(dtf_order, dtf_distances)
    return _df_to_pydantic(dtf_final, OptimizationResponse)


@audit_event('OPTIMIZATION', 'OptimalRoute', 'READ')
async def optimization_algorithm_controller(
    dynamodb_resource: ServiceResource,
    route_id: int,
    day: int,
    dist: int
) -> Optional[List[RouteResponse]]:
    '''
        Runs the full route-optimization pipeline (ordering + OSRM projection).

        `dist` is kept for backward compatibility with the legacy OSM-graph
        radius contract but no longer affects routing: OSRM resolves the full
        street geometry for every segment regardless of any radius.
    '''
    dtf_final_models = await data_ordered_controller(dynamodb_resource, route_id, day)
    dtf_final = pd.DataFrame([m.model_dump() for m in dtf_final_models])
    dtf_route = _final_route(dtf_final)
    return _df_to_pydantic(dtf_route, RouteResponse)


async def simulation_algorithm_controller(
    dynamodb_resource: ServiceResource,
    route_id: int,
    day: int
) -> dict:
    '''
        Returns the geodesic distance matrix between all client points
        (output of GeoAnalyzer.get_distance_matrix as a dict).
    '''
    dtf = _load_dataframe(dynamodb_resource, route_id, day)
    data = _draw_map(dtf)

    distance_matrix = data[data['day'] == day][['client_id', 'y', 'x']].reset_index(
        drop = True
    )
    distance_matrix = distance_matrix.rename(columns = {'y': 'latitude', 'x': 'longitude'})
    distance_matrix = distance_matrix.set_index('client_id')

    geo_analyzer = GeoAnalyzer()
    geo_analyzer.add_locations(distance_matrix)

    df_distances = geo_analyzer.get_distance_matrix()
    return df_distances.to_dict()


# ---------------------------------------------------------------------------
# Bulk upload — CSV → DynamoDB
# ---------------------------------------------------------------------------
_COLUMN_ALIASES = {
    'route_id':  ['route_id', 'routeid', 'ruta', 'ruta_id', 'rutaid'],
    'day':       ['day', 'dia', 'día', 'jornada'],
    'client_id': ['client_id', 'clientid', 'cliente_id', 'cliente', 'id_cliente', 'id'],
    'latitude':  ['latitude', 'lat', 'latitud', 'y'],
    'longitude': ['longitude', 'lon', 'lng', 'longitud', 'x'],
    'client':    ['client', 'cliente_nombre', 'nombre', 'name']
}
REQUIRED_COLUMNS = {'route_id', 'day', 'client_id', 'latitude', 'longitude'}


def _resolve_header(raw_header: str) -> Optional[str]:
    '''
        Maps a CSV header column to its canonical name. Returns None when
        the header is not part of the recognized set.
    '''
    norm = raw_header.strip().lower()
    for canonical, aliases in _COLUMN_ALIASES.items():
        if norm in aliases:
            return canonical
    return None


def _parse_csv_text(raw_text: str) -> Tuple[List[dict], List[str], int, int]:
    '''
        Parses the CSV body. Returns:
            - rows: list of dicts keyed by canonical column name
            - detected_headers: canonical headers that appeared in the file
            - route_id_detected
            - day_detected
        Raises InvalidInputError on missing required columns or mixed
        (route_id, day) values across the file.
    '''
    reader = csv.reader(io.StringIO(raw_text))
    rows_iter = iter(reader)
    try:
        header = next(rows_iter)
    except StopIteration as e:
        raise InvalidInputError(detail = 'El archivo CSV está vacío.') from e

    resolved = [_resolve_header(cell) for cell in header]
    canonical_set = {col for col in resolved if col}
    missing = REQUIRED_COLUMNS - canonical_set
    if missing:
        raise InvalidInputError(
            detail = (
                f'Faltan columnas obligatorias en el CSV: {sorted(missing)}. '
                f'Columnas detectadas: {sorted(canonical_set)}.'
            )
        )

    rows: List[dict] = []
    route_id_set = set()
    day_set = set()
    for line_no, raw_row in enumerate(rows_iter, start = 2):
        if not raw_row or all((cell or '').strip() == '' for cell in raw_row):
            continue
        record: dict = {}
        for idx, value in enumerate(raw_row):
            if idx >= len(resolved):
                continue
            col = resolved[idx]
            if col is None:
                continue
            record[col] = (value or '').strip()
        try:
            record['route_id'] = int(record['route_id'])
            record['day'] = int(record['day'])
            record['client_id'] = int(record['client_id'])
            record['latitude'] = float(record['latitude'])
            record['longitude'] = float(record['longitude'])
        except (KeyError, ValueError) as e:
            raise InvalidInputError(
                detail = f'Fila {line_no} con valores inválidos ({e}).'
            ) from e
        route_id_set.add(record['route_id'])
        day_set.add(record['day'])
        rows.append(record)

    if not rows:
        raise InvalidInputError(detail = 'El CSV no contiene filas de datos.')
    if len(route_id_set) != 1 or len(day_set) != 1:
        raise InvalidInputError(
            detail = (
                'Todos los puntos del CSV deben compartir el mismo route_id y day. '
                f'route_id encontrados: {sorted(route_id_set)}; '
                f'day encontrados: {sorted(day_set)}.'
            )
        )
    return (
        rows,
        sorted(canonical_set),
        next(iter(route_id_set)),
        next(iter(day_set))
    )


@audit_event('OPTIMIZATION', 'RoutePoints', 'BULK_CREATE')
async def bulk_upload_routes_controller(
    dynamodb_resource: ServiceResource,
    csv_text: str,
    current_user: str
) -> BulkUploadResponse:
    '''
        Parses a CSV body and persists every point into DynamoDB under the
        (route_id, day) partition. Re-uploading the same (route_id, day)
        replaces the previous content.

        `current_user` is accepted so the @audit_event decorator can stamp
        the event with the operator email.
    '''
    rows, headers, route_id, day = _parse_csv_text(csv_text)
    written = bulk_upload_points(
        dynamodb_resource = dynamodb_resource,
        route_id = route_id,
        day = day,
        points = rows
    )
    return BulkUploadResponse(
        route_id = route_id,
        day = day,
        points_written = written,
        columns_detected = headers
    )
