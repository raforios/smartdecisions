'''
    Optimization domain — main module.

    Turns the normalized sales dataset into a visit plan: which clients belong
    to which day (by geography), in what order to visit them, and the real road
    route between stops. Also holds the bulk-upload parser for pre-planned
    routes and the map/distance helpers the simulation endpoints use.

    Route planner — turns a sales dataset into a week of visit routes.

    The previous module asked the user for a `route_id` and a `day` and read the
    points from a DynamoDB table seeded separately, so the map had nothing to do
    with the sales file the user had just uploaded. Here the plan is derived
    entirely from that file: the clients are the ones who actually bought, the
    days are inferred from where those clients are, and each stop carries what
    the rest of the platform already knows about it — how much it buys and how
    valuable it is.

    Two algorithms, both implemented locally because the libraries that provide
    them (`osmnx`, `networkx`, `scikit-learn`, OR-Tools) do not fit in the
    250 MB Lambda budget:

      * **k-means on the sphere** to split the clients into daily clusters, so a
        day's stops are geographically close instead of scattered across the city.
      * **Nearest neighbour + 2-opt** to order the stops within a day. Nearest
        neighbour alone is what produced the crossing lines in the old map;
        2-opt removes them by repeatedly reversing any segment that shortens the
        tour.
'''
import csv
import io
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from schemas.optimization import DayRoute, RouteStop, OptimizationError
from services.environment import load_and_validate_env_vars
from services.exceptions import InvalidInputError
from services.logger_config import custom_logger as logger
from services.route_algorithm import distance_between_points, optimal_route
from services.routing import road_segment, road_trip


# Canonical columns written by the ingest normalization.
DATE = 'date'
CLIENT_ID = 'pos_id'
CLIENT_NAME = 'pos_name'
AMOUNT = 'total_amount'
SELLER = 'seller'
LATITUDE = 'latitude'
LONGITUDE = 'longitude'

EARTH_RADIUS_M: float = 6_371_000.0

# Operational knobs. How many visits fit in a rep's day, and where the value
# tiers are cut, are decisions of the business being served — not of this code.
#
# The tier variables carry the SAME names the ANALYTICS service uses for its
# segmentation module. That is deliberate: a client shown as 'HIGH' on the
# segmentation screen must be 'HIGH' on the map. Two services means two .env
# files, so the values have to be kept in step in both.
# Required, not optional: a fallback written in code is still a number chosen
# by the code. If one is missing the service must say so at startup.
ENV_VARS = load_and_validate_env_vars({
    'SEGMENTATION_HIGH_TOP_SHARE': float,
    'SEGMENTATION_MEDIUM_TOP_SHARE': float,
    'ROUTES_MAX_STOPS_PER_DAY': int,
    'CLUSTER_SEED': int,
    'AMOUNT_DECIMALS': int,
    'DURATION_DECIMALS': int,
    'ROUTES_KMEANS_ITERATIONS': int,
    'ROUTES_TWO_OPT_PASSES': int,
})

# Fixed so the same points always produce the same grouping: a plan that
# reshuffles between two identical runs is impossible to trust or to support.
CLUSTER_SEED = ENV_VARS['CLUSTER_SEED']

# Decimals a money figure and a duration carry in a response.
AMOUNT_DECIMALS = ENV_VARS['AMOUNT_DECIMALS']
DURATION_DECIMALS = ENV_VARS['DURATION_DECIMALS']

# Unit conversions, not decisions.
METRES_PER_KM = 1000
SECONDS_PER_MINUTE = 60


# A client in the top 20% by purchase value is 'HIGH'; the quantile is the
# complement of that share.
_HIGH_VALUE_QUANTILE: float = 1 - ENV_VARS['SEGMENTATION_HIGH_TOP_SHARE']
_MID_VALUE_QUANTILE: float = 1 - ENV_VARS['SEGMENTATION_MEDIUM_TOP_SHARE']
_MAX_STOPS_PER_DAY: int = ENV_VARS['ROUTES_MAX_STOPS_PER_DAY']

# Algorithm internals: these bound the search, they do not change what the
# product reports. 2-opt is O(n^2) per pass; a day's route is tens of stops, so
# a handful of passes converges well within the request budget.
_KMEANS_ITERATIONS: int = ENV_VARS['ROUTES_KMEANS_ITERATIONS']
_TWO_OPT_PASSES: int = ENV_VARS['ROUTES_TWO_OPT_PASSES']


def haversine_matrix(points: np.ndarray) -> np.ndarray:
    '''
        Great-circle distance in metres between every pair of points.

        Args:
            points (np.ndarray): Array of shape (n, 2) holding (lat, lon) in
                degrees.

        Returns:
            np.ndarray: Symmetric (n, n) distance matrix in metres.
    '''
    radians = np.radians(points)
    lat = radians[:, 0][:, None]
    lon = radians[:, 1][:, None]
    delta_lat = lat - lat.T
    delta_lon = lon - lon.T
    inner = (
        np.sin(delta_lat / 2) ** 2
        + np.cos(lat) * np.cos(lat.T) * np.sin(delta_lon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * np.arcsin(np.sqrt(np.clip(inner, 0, 1)))


def _kmeans(
    points: np.ndarray,
    clusters: int,
    seed: int = CLUSTER_SEED
) -> np.ndarray:
    '''
        Groups points into `clusters` geographic clusters (Lloyd's algorithm).

        Implemented here rather than pulled from scikit-learn, whose transitive
        dependencies blow past the Lambda size limit.

        Args:
            points (np.ndarray): Array of shape (n, 2) with (lat, lon).
            clusters (int): Number of clusters wanted.
            seed (int): Seed making the assignment reproducible.

        Returns:
            np.ndarray: Cluster index per point.
    '''
    count = len(points)
    if clusters <= 1 or count <= clusters:
        return np.arange(count) % max(clusters, 1)

    rng = np.random.default_rng(seed)
    centroids = points[rng.choice(count, size = clusters, replace = False)]
    labels = np.zeros(count, dtype = int)

    for _ in range(_KMEANS_ITERATIONS):
        distances = np.linalg.norm(points[:, None, :] - centroids[None, :, :], axis = 2)
        updated = distances.argmin(axis = 1)
        if np.array_equal(updated, labels):
            break
        labels = updated
        for index in range(clusters):
            member = points[labels == index]
            if len(member):
                centroids[index] = member.mean(axis = 0)
    return labels


def _balance_clusters(points: np.ndarray, labels: np.ndarray, clusters: int) -> np.ndarray:
    '''
        Evens out the cluster sizes so no day carries the whole city.

        Plain k-means optimises compactness and nothing else, which on real
        client geography produced days of 8 and 97 stops — a plan no rep can
        work. Points furthest from their own centroid are handed to the nearest
        cluster that still has room, which costs a little compactness and buys
        a schedule that can actually be executed.

        Args:
            points (np.ndarray): Array of shape (n, 2) with (lat, lon).
            labels (np.ndarray): Cluster index per point.
            clusters (int): Number of clusters.

        Returns:
            np.ndarray: Balanced cluster index per point.
    '''
    labels = labels.copy()
    capacity = int(np.ceil(len(points) / clusters))

    for _ in range(clusters):
        sizes = np.bincount(labels, minlength = clusters)
        crowded = [index for index in range(clusters) if sizes[index] > capacity]
        if not crowded:
            break

        centroids = np.array([
            points[labels == index].mean(axis = 0) if sizes[index] else points.mean(axis = 0)
            for index in range(clusters)
        ])
        for source in crowded:
            members = np.flatnonzero(labels == source)
            spread = np.linalg.norm(points[members] - centroids[source], axis = 1)
            for member in members[np.argsort(-spread)][:sizes[source] - capacity]:
                filled = np.bincount(labels, minlength = clusters)
                room = [
                    index for index in range(clusters)
                    if index != source and filled[index] < capacity
                ]
                if not room:
                    break
                distances = np.linalg.norm(centroids[room] - points[member], axis = 1)
                labels[member] = room[int(np.argmin(distances))]
    return labels


def _nearest_neighbour(distances: np.ndarray) -> List[int]:
    '''
        Builds an initial tour by always hopping to the closest unvisited stop.

        Args:
            distances (np.ndarray): Square distance matrix.

        Returns:
            List[int]: Visit order as indices into the matrix.
    '''
    count = len(distances)
    unvisited = set(range(1, count))
    tour = [0]
    while unvisited:
        current = tour[-1]
        nearest = min(unvisited, key = lambda index: distances[current][index])
        tour.append(nearest)
        unvisited.remove(nearest)
    return tour


def _two_opt(tour: List[int], distances: np.ndarray) -> List[int]:
    '''
        Removes crossings from a tour by reversing any segment that shortens it.

        This is the fix for the "diagram full of crossing lines" the old module
        drew: those crossings are not a rendering artefact, they are what a
        greedy nearest-neighbour tour looks like.

        Args:
            tour (List[int]): Initial visit order.
            distances (np.ndarray): Square distance matrix.

        Returns:
            List[int]: Improved visit order.
    '''
    best = tour[:]
    for _ in range(_TWO_OPT_PASSES):
        improved = False
        # The route is an OPEN path: the rep starts at the first stop and ends
        # at the last, they do not drive back. Treating it as a closed loop
        # optimised the wrong quantity and could leave the real path longer
        # than the greedy tour it started from.
        for first in range(1, len(best) - 1):
            for second in range(first + 1, len(best) - 1):
                a, b = best[first - 1], best[first]
                c, d = best[second], best[second + 1]
                current = distances[a][b] + distances[c][d]
                swapped = distances[a][c] + distances[b][d]
                if swapped < current - 1e-9:
                    best[first:second + 1] = reversed(best[first:second + 1])
                    improved = True
        if not improved:
            break
    return best


def order_stops(points: np.ndarray) -> List[int]:
    '''
        Produces the visit order for one day's stops.

        Args:
            points (np.ndarray): Array of shape (n, 2) with (lat, lon).

        Returns:
            List[int]: Visit order as indices into `points`.
    '''
    if len(points) <= 2:
        return list(range(len(points)))
    distances = haversine_matrix(points)
    return _two_opt(_nearest_neighbour(distances), distances)


def _value_tier(amount: float, thresholds: Tuple[float, float]) -> str:
    '''
        Labels a client by purchase value, using the same cut-offs as the
        segmentation module.

        Args:
            amount (float): The client's total purchases in the period.
            thresholds (tuple): (high cut-off, mid cut-off).

        Returns:
            str: 'HIGH', 'MEDIUM' or 'LOW'.
    '''
    if amount >= thresholds[0]:
        return 'HIGH'
    if amount >= thresholds[1]:
        return 'MEDIUM'
    return 'LOW'


def build_client_points(dataframe: pd.DataFrame, seller: Optional[str] = None) -> pd.DataFrame:
    '''
        Collapses the sales rows into one geolocated row per client, carrying
        what the visit is worth.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows from ingest.
            seller (str | None): Restrict to one salesperson's clients.

        Returns:
            pd.DataFrame: One row per client with coordinates, amount, order
                count, last purchase and value tier.

        Raises:
            InvalidInputError: If the file carries no usable coordinates.
    '''
    required = {CLIENT_ID, LATITUDE, LONGITUDE}
    if not required.issubset(dataframe.columns):
        raise InvalidInputError(detail = OptimizationError.MISSING_COORDINATES.value)

    scoped = dataframe
    if seller and SELLER in scoped.columns:
        scoped = scoped[scoped[SELLER].astype(str) == str(seller)]

    scoped = scoped[scoped[LATITUDE].notna() & scoped[LONGITUDE].notna()]
    if scoped.empty:
        raise InvalidInputError(
            detail = OptimizationError.NO_GEOCODED_CLIENTS.value
        )

    grouped = scoped.groupby(CLIENT_ID)
    clients = pd.DataFrame({
        'latitude': grouped[LATITUDE].median(),
        'longitude': grouped[LONGITUDE].median(),
        'amount': grouped[AMOUNT].sum() if AMOUNT in scoped.columns else 0.0,
    })
    clients['client_name'] = (
        grouped[CLIENT_NAME].first() if CLIENT_NAME in scoped.columns
        else clients.index.astype(str)
    )
    clients['last_purchase'] = (
        pd.to_datetime(grouped[DATE].max(), errors = 'coerce')
        if DATE in scoped.columns else pd.NaT
    )

    thresholds = (
        float(clients['amount'].quantile(_HIGH_VALUE_QUANTILE)),
        float(clients['amount'].quantile(_MID_VALUE_QUANTILE)),
    )
    clients['segment'] = clients['amount'].map(lambda value: _value_tier(value, thresholds))
    return clients.reset_index().rename(columns = {CLIENT_ID: 'client_id'})


def assign_days(clients: pd.DataFrame, days: int) -> pd.DataFrame:
    '''
        Splits the clients into daily routes by geographic proximity.

        Days are *derived*, not read from the file: a client's route and visit
        day are an operational decision, and inferring them from where the
        clients are means the module works with any sales export, with or
        without route columns of its own.

        Args:
            clients (pd.DataFrame): One row per client, from build_client_points.
            days (int): Number of visit days to spread the clients over.

        Returns:
            pd.DataFrame: The same frame with a 'day' column (1-based).
    '''
    coordinates = clients[['latitude', 'longitude']].to_numpy(dtype = float)
    labels = _balance_clusters(coordinates, _kmeans(coordinates, days), days)

    clients = clients.copy()
    clients['day'] = labels + 1

    message = f'Route plan: {len(clients)} clients grouped into {days} day(s).'
    logger.info(message)
    return clients


def _stop_payload(row: pd.Series, position: int) -> RouteStop:
    '''
        Shapes one stop of the visit plan.

        Args:
            row (pd.Series): The client's row.
            position (int): 1-based position within the day's route.

        Returns:
            RouteStop: The stop as the API returns it.
    '''
    last = row.get('last_purchase')
    return RouteStop(
        stop_order = position,
        client_id = str(row['client_id']),
        client = str(row['client_name']),
        latitude = float(row['latitude']),
        longitude = float(row['longitude']),
        amount = round(float(row['amount']), AMOUNT_DECIMALS),
        segment = str(row['segment']),
        last_purchase = None if pd.isna(last) else pd.Timestamp(last).strftime('%Y-%m-%d')
    )


def plan_day(clients: pd.DataFrame, day: int) -> List[RouteStop]:
    '''
        Orders one day's stops and shapes them for the response.

        Args:
            clients (pd.DataFrame): Clients already assigned to days.
            day (int): The day to plan (1-based).

        Returns:
            List[RouteStop]: Ordered stops of that day.
    '''
    scoped = clients[clients['day'] == day]
    if scoped.empty:
        return []

    # A single day cannot hold an unbounded number of visits, and the distance
    # matrix is quadratic; keep the highest-value stops when it overflows.
    if len(scoped) > _MAX_STOPS_PER_DAY:
        scoped = scoped.nlargest(_MAX_STOPS_PER_DAY, 'amount')

    coordinates = scoped[['latitude', 'longitude']].to_numpy(dtype = float)
    order = order_stops(coordinates)
    rows = scoped.iloc[order].reset_index(drop = True)
    return [_stop_payload(row, position + 1) for position, row in rows.iterrows()]


# ---------------------------------------------------------------------------
# Business logic previously living in the controller
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Algorithm helpers (verbatim from monolith)
# ---------------------------------------------------------------------------
def tag_map_colors(dtf: pd.DataFrame) -> pd.DataFrame:
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


def build_distance_matrix(dtf: pd.DataFrame) -> pd.DataFrame:
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


def order_route(dtf: pd.DataFrame, dtf_distances: pd.DataFrame) -> pd.DataFrame:
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


def resolve_road_route(dtf: pd.DataFrame) -> pd.DataFrame:
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




# Accepted headers for the bulk route CSV. Same contract as everywhere else:
# the client fills in the format we publish.
_COLUMN_ALIASES = {
    'route_id':  ['route_id', 'routeid'],
    'day':       ['day'],
    'client_id': ['client_id', 'clientid', 'id'],
    'latitude':  ['latitude', 'lat', 'y'],
    'longitude': ['longitude', 'lon', 'lng', 'x'],
    'client':    ['client', 'client_name', 'name']
}
REQUIRED_COLUMNS = {'route_id', 'day', 'client_id', 'latitude', 'longitude'}


def _resolve_route_header(raw_header: str) -> Optional[str]:
    '''
        Maps a CSV header column to its canonical name. Returns None when
        the header is not part of the recognized set.
    '''
    norm = raw_header.strip().lower()
    for canonical, aliases in _COLUMN_ALIASES.items():
        if norm in aliases:
            return canonical
    return None


def _resolve_and_validate_route_header(header: List[str]) -> List[Optional[str]]:
    '''
        Maps each raw header cell to its canonical name and ensures every
        required column is present.

        Raises:
            InvalidInputError: If a mandatory column is missing.
    '''
    resolved = [_resolve_route_header(cell) for cell in header]
    canonical_set = {col for col in resolved if col}
    missing = REQUIRED_COLUMNS - canonical_set
    if missing:
        raise InvalidInputError(
            detail = (
                f'Faltan columnas obligatorias en el CSV: {sorted(missing)}. '
                f'Columnas detectadas: {sorted(canonical_set)}.'
            )
        )
    return resolved


def _parse_route_csv_row(
    raw_row: List[str],
    resolved: List[Optional[str]],
    line_no: int
) -> dict:
    '''
        Builds a single canonical record from a raw CSV row, coercing the
        numeric columns.

        Raises:
            InvalidInputError: If a row has non-numeric or missing values.
    '''
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
        # The offending line number stays in the log; the client gets the code.
        error_msg = f'Row {line_no} of the route CSV carries invalid values: {e}'
        logger.warning(error_msg)
        raise InvalidInputError(detail = OptimizationError.INVALID_ROW.value) from e
    return record


def parse_route_csv(raw_text: str) -> Tuple[List[dict], List[str], int, int]:
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
        raise InvalidInputError(detail = OptimizationError.EMPTY_CSV.value) from e

    resolved = _resolve_and_validate_route_header(header)

    rows: List[dict] = []
    for line_no, raw_row in enumerate(rows_iter, start = 2):
        if not raw_row or all((cell or '').strip() == '' for cell in raw_row):
            continue
        rows.append(_parse_route_csv_row(raw_row, resolved, line_no))

    if not rows:
        raise InvalidInputError(detail = 'El CSV no contiene filas de datos.')

    route_id_set = {record['route_id'] for record in rows}
    day_set = {record['day'] for record in rows}
    if len(route_id_set) != 1 or len(day_set) != 1:
        raise InvalidInputError(
            detail = (
                'Todos los puntos del CSV deben compartir el mismo route_id y day. '
                f'route_id encontrados: {sorted(route_id_set)}; '
                f'day encontrados: {sorted(day_set)}.'
            )
        )

    canonical_set = sorted({col for col in resolved if col})
    return rows, canonical_set, next(iter(route_id_set)), next(iter(day_set))


def scope_to_period(dataframe: pd.DataFrame, params: dict) -> pd.DataFrame:
    '''
        Narrows the sales rows to the requested date window.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows.
            params (dict): May carry 'date_from' and 'date_to'.

        Returns:
            pd.DataFrame: Rows inside the window (all of them when unset).
    '''
    if DATE not in dataframe.columns:
        return dataframe

    parsed = pd.to_datetime(dataframe[DATE], errors = 'coerce')
    mask = parsed.notna()
    if params.get('date_from'):
        mask &= parsed >= pd.Timestamp(params['date_from'])
    if params.get('date_to'):
        mask &= parsed <= pd.Timestamp(params['date_to'])

    scoped = dataframe[mask]
    if scoped.empty:
        raise InvalidInputError(
            detail = OptimizationError.EMPTY_PERIOD.value
        )
    return scoped


def available_sellers(dataframe: pd.DataFrame) -> List[str]:
    '''
        Lists the salespeople present in the dataset, for the UI selector.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows.

        Returns:
            List[str]: Sorted, de-duplicated salesperson names.
    '''
    if SELLER not in dataframe.columns:
        return []
    names = dataframe[SELLER].dropna().astype(str).str.strip()
    return sorted({name for name in names if name})


def build_day(clients: pd.DataFrame, day: int) -> DayRoute:
    '''
        Orders one day's stops and projects the trip onto the road network.

        Args:
            clients (pd.DataFrame): Clients already assigned to days.
            day (int): Day number (1-based).

        Returns:
            DayRoute: The day's stops, totals and street geometry.
    '''
    stops = plan_day(clients, int(day))
    if not stops:
        return DayRoute(day = int(day))

    trip = road_trip([(stop.latitude, stop.longitude) for stop in stops])
    return DayRoute(
        day = int(day),
        stops = stops,
        distance_km = round(trip['distance'] / METRES_PER_KM, AMOUNT_DECIMALS),
        duration_min = round(trip['duration'] / SECONDS_PER_MINUTE, DURATION_DECIMALS),
        total_amount = round(sum(stop.amount for stop in stops), AMOUNT_DECIMALS),
        geometry = trip['geometry']
    )
