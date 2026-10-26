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

    Two algorithms, asked of ML_FUNCTIONS since 24-oct-2026 (Rafael, 21-oct:
    the route algorithm belongs there), with the caller's token:

      * **balanced k-means** (`/v1/routing/clusters`) to split the clients into
        daily clusters, so a day's stops are geographically close instead of
        scattered across the city.
      * **Nearest neighbour + 2-opt** (`/v1/routing/order`) to order the stops
        within a day, without the crossing lines the greedy tour alone draws.

    The value tier of each stop is the segmentation's, asked of ML_FUNCTIONS
    with the same cuts, so a client is the same tier on the map and on the
    segmentation screen.
'''
import numpy as np
import pandas as pd

from schemas.optimization import DayRoute, RouteStop, OptimizationError
from services.calculations import ask_ml_functions, rank_tiers
from services.utils import load_parameters
from services.exceptions import InvalidInputError
from services.logger_config import custom_logger as logger
from services.routing import road_trip


# Canonical columns written by the ingest normalization.
DATE = 'date'
CLIENT_ID = 'pos_id'
CLIENT_NAME = 'pos_name'
AMOUNT = 'total_amount'
SELLER = 'seller'
LATITUDE = 'latitude'
LONGITUDE = 'longitude'

# Operational knobs. How many visits fit in a rep's day, and where the value
# tiers are cut, are decisions of the business being served — not of this code.
#
# The tier variables are the segmentation's own: a client shown as 'HIGH' on
# the segmentation screen must be 'HIGH' on the map.
# Required, not optional: a fallback written in code is still a number chosen
# by the code. If one is missing the service must say so at startup.
ENV_VARS = load_parameters({
    'SEGMENTATION_HIGH_TOP_SHARE': float,
    'SEGMENTATION_MEDIUM_TOP_SHARE': float,
    'ROUTES_MAX_STOPS_PER_DAY': int,
    'CLUSTER_SEED': int,
    'AMOUNT_DECIMALS': int,
    'DURATION_DECIMALS': int,
    'ROUTES_KMEANS_ITERATIONS': int,
    'ROUTES_TWO_OPT_PASSES': int
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


# Where the value ranking is cut, top first, and the name of each tier.
_TIER_CUTS: list[float] = [ENV_VARS['SEGMENTATION_HIGH_TOP_SHARE'],
                           ENV_VARS['SEGMENTATION_MEDIUM_TOP_SHARE']]
_TIER_NAMES: tuple[str, ...] = ('HIGH', 'MEDIUM', 'LOW')
_MAX_STOPS_PER_DAY: int = ENV_VARS['ROUTES_MAX_STOPS_PER_DAY']

# Bounds of the search ML_FUNCTIONS runs; they do not change what the product
# reports. 2-opt is O(n^2) per pass; a day's route is tens of stops, so a
# handful of passes converges well within the request budget.
_KMEANS_ITERATIONS: int = ENV_VARS['ROUTES_KMEANS_ITERATIONS']
_TWO_OPT_PASSES: int = ENV_VARS['ROUTES_TWO_OPT_PASSES']


def order_stops(
    points: np.ndarray,
    auth_token: str
) -> list[int]:
    '''
        Produces the visit order for one day's stops, asked of ML_FUNCTIONS.

        Args:
            points (np.ndarray): Array of shape (n, 2) with (lat, lon).
            auth_token (str): The caller's Authorization header.

        Returns:
            list[int]: Visit order as indices into `points`.
    '''
    if len(points) <= 2:
        return list(range(len(points)))
    answer = ask_ml_functions('/v1/routing/order',
                              {'points': np.asarray(points, dtype = float).tolist(),
                               'passes': _TWO_OPT_PASSES},
                              auth_token, OptimizationError.CALCULATION_UNAVAILABLE.value)
    return [int(index) for index in answer['order']]


def build_client_points(
    dataframe: pd.DataFrame,
    auth_token: str,
    seller: str | None = None
) -> pd.DataFrame:
    '''
        Collapses the sales rows into one geolocated row per client, carrying
        what the visit is worth.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows from ingest.
            auth_token (str): The caller's Authorization header, for ML_FUNCTIONS.
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

    tiers = rank_tiers([float(value) for value in clients['amount']], _TIER_CUTS, auth_token,
                       OptimizationError.CALCULATION_UNAVAILABLE.value)
    clients['segment'] = [_TIER_NAMES[tier] for tier in tiers]
    return clients.reset_index().rename(columns = {CLIENT_ID: 'client_id'})


def assign_days(
    clients: pd.DataFrame,
    days: int,
    auth_token: str
) -> pd.DataFrame:
    '''
        Splits the clients into daily routes by geographic proximity.

        Days are *derived*, not read from the file: a client's route and visit
        day are an operational decision, and inferring them from where the
        clients are means the module works with any sales export, with or
        without route columns of its own.

        Args:
            clients (pd.DataFrame): One row per client, from build_client_points.
            days (int): Number of visit days to spread the clients over.
            auth_token (str): The caller's Authorization header, for ML_FUNCTIONS.

        Returns:
            pd.DataFrame: The same frame with a 'day' column (1-based).
    '''
    answer = ask_ml_functions(
        '/v1/routing/clusters',
        {'points': clients[['latitude', 'longitude']].to_numpy(dtype = float).tolist(),
         'clusters': days, 'seed': CLUSTER_SEED, 'iterations': _KMEANS_ITERATIONS},
        auth_token, OptimizationError.CALCULATION_UNAVAILABLE.value)

    clients = clients.copy()
    clients['day'] = [int(label) + 1 for label in answer['labels']]

    message = f'Route plan: {len(clients)} clients grouped into {days} day(s).'
    logger.info(message)
    return clients


def _stop_payload(
    row: pd.Series,
    position: int
) -> RouteStop:
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


def plan_day(
    clients: pd.DataFrame,
    day: int,
    auth_token: str
) -> list[RouteStop]:
    '''
        Orders one day's stops and shapes them for the response.

        Args:
            clients (pd.DataFrame): Clients already assigned to days.
            day (int): The day to plan (1-based).
            auth_token (str): The caller's Authorization header, for ML_FUNCTIONS.

        Returns:
            list[RouteStop]: Ordered stops of that day.
    '''
    scoped = clients[clients['day'] == day]
    if scoped.empty:
        return []

    # A single day cannot hold an unbounded number of visits, and the distance
    # matrix is quadratic; keep the highest-value stops when it overflows.
    if len(scoped) > _MAX_STOPS_PER_DAY:
        scoped = scoped.nlargest(_MAX_STOPS_PER_DAY, 'amount')

    coordinates = scoped[['latitude', 'longitude']].to_numpy(dtype = float)
    order = order_stops(coordinates, auth_token)
    rows = scoped.iloc[order].reset_index(drop = True)
    return [_stop_payload(row, position + 1) for position, row in rows.iterrows()]


# ---------------------------------------------------------------------------
# Business logic previously living in the controller
# ---------------------------------------------------------------------------

def scope_to_period(
    dataframe: pd.DataFrame,
    params: dict
) -> pd.DataFrame:
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


def available_sellers(dataframe: pd.DataFrame) -> list[str]:
    '''
        Lists the salespeople present in the dataset, for the UI selector.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows.

        Returns:
            list[str]: Sorted, de-duplicated salesperson names.
    '''
    if SELLER not in dataframe.columns:
        return []
    names = dataframe[SELLER].dropna().astype(str).str.strip()
    return sorted({name for name in names if name})


def build_day(
    clients: pd.DataFrame,
    day: int,
    auth_token: str
) -> DayRoute:
    '''
        Orders one day's stops and projects the trip onto the road network.

        Args:
            clients (pd.DataFrame): Clients already assigned to days.
            day (int): Day number (1-based).
            auth_token (str): The caller's Authorization header, for ML_FUNCTIONS.

        Returns:
            DayRoute: The day's stops, totals and street geometry.
    '''
    stops = plan_day(clients, int(day), auth_token)
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
