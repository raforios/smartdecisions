'''
    ML Route Optimization Algorithm

    Ported verbatim from the legacy monolith (`api/services/ml_optimization.py`).
    Only the imports were adjusted to the microservice tree; the math and the
    interfaces are unchanged so existing notebook contracts keep working.
'''
import random
import pandas as pd
from geopy.distance import geodesic


# ----------------------------------------------------------------
# Distance calculation given 2 points
# ----------------------------------------------------------------
def distance_between_points(node_1: tuple, node_2: tuple) -> float:
    '''
        Distance between node1 and node2 using geodesic distance.

        Args:
            node_1 (tuple): (latitude, longitude) of the first point.
            node_2 (tuple): (latitude, longitude) of the second point.

        Returns:
            float: Geodesic distance in meters.
    '''
    return geodesic(node_1, node_2).meters


# ----------------------------------------------------------------
# Generating Hexadecimal colors
# ----------------------------------------------------------------
def hexa_color_generator() -> str:
    '''
        Create a single random color in hex format.
    '''
    red = random.randint(0, 255)
    green = random.randint(0, 255)
    blue = random.randint(0, 255)
    return f'#{red:02x}{green:02x}{blue:02x}'


def hexa_color_generator_list(quantity: int) -> list:
    '''
        Generates a list of unique hexadecimal colors.

        Args:
            quantity (int): Number of unique colors to produce.

        Returns:
            list: Hex color strings.
    '''
    colors = set()
    while len(colors) < quantity:
        red = random.randint(0, 255)
        green = random.randint(0, 255)
        blue = random.randint(0, 255)
        colors.add(f'#{red:02x}{green:02x}{blue:02x}')
    return list(colors)


# ----------------------------------------------------------------
# GeoAnalyzer Class
# ----------------------------------------------------------------
class GeoAnalyzer:
    '''
        Utils for geolocation information and processing.
    '''
    def __init__(self):
        '''
            Use method `add_locations` to store some locations inside
            and start using the geo-utilities.
        '''
        self._df_locations = pd.DataFrame(columns = ['latitude', 'longitude'])
        self._name_index = ''

    @property
    def locations(self):
        '''
            Returns the geographical coordinates DataFrame.
        '''
        return self._df_locations

    @property
    def num_locations(self):
        '''
            Returns the number of geographical coordinates stored.
        '''
        return len(self._df_locations)

    def add_locations(self, df_locations: pd.DataFrame):
        '''
            Stores the geo-location data needed for analysis.

            Args:
                df_locations (pd.DataFrame): Dataframe of geographical
                    coordinates with the first column named 'latitude' and the
                    second column named 'longitude'.
        '''
        self._name_index = df_locations.index.name
        df1 = self._df_locations.dropna(axis = 1, how = 'all')
        df2 = df_locations.copy().dropna(axis = 1, how = 'all')
        df_updated = pd.concat([df1, df2])
        self._df_locations = df_updated.drop_duplicates()

    def get_distance_matrix(self, precision: int = 4) -> pd.DataFrame:
        '''
            Computes the distance matrix as a dataframe based on the provided
            location data.
        '''
        df_locations = self._df_locations
        dist_metric = distance_between_points

        df_dist_matrix = pd.DataFrame(
            index = df_locations.index,
            columns = df_locations.index
        )
        for orig, orig_loc in df_locations.iterrows():
            for dest, dest_loc in df_locations.iterrows():
                distance = round(dist_metric(orig_loc, dest_loc), precision)
                df_dist_matrix.at[orig, dest] = distance

        df_dist_matrix.distance_metric = dist_metric.__name__
        df_dist_matrix.index.name = self._name_index
        return df_dist_matrix

    def __repr__(self):
        '''
            Display number of currently considered locations.
        '''
        return f'{self.__class__.__name__}(n_locs = {self.num_locations})'


# ----------------------------------------------------------------
# Building route between two points
# ----------------------------------------------------------------
def build_route_object(origins: list, data: dict, counter: int, values: list, df):
    '''
        Build route object using data from a dataset.
    '''
    new_row = pd.DataFrame(data, index = [counter + 1])
    origins.append(values[0])
    origin = values[1]
    destination = values[2]
    df = pd.concat([df, new_row], ignore_index = True)
    return df, origin, destination, origins


# ----------------------------------------------------------------
# Filtering and ordering a given dataframe
# ----------------------------------------------------------------
def fiter_order_df(filter_exp, orderby: str, df: pd.DataFrame, sort = True) -> pd.DataFrame:
    '''
        Create a new dataframe from a given dataframe using a filter and
        ordering it.
    '''
    df_result = df[filter_exp]
    df_result_order = df_result.sort_values(by = orderby, ascending = sort)
    return df_result_order.reset_index(drop = True)


# ----------------------------------------------------------------
# Optimal route algorithm
# ----------------------------------------------------------------
def optimal_route(size: int, origin: int, target: int, df_distances: pd.DataFrame,
                  df_order: pd.DataFrame) -> pd.DataFrame:
    '''
        Create traffic route data from a given dataframe.
    '''
    counter = 0
    origins: list = []
    values: list = []
    # df_id is only read by the distance == 2 / == 3 branches below, which
    # always assign it first; it is seeded here so static analysis can prove
    # it is bound before the match without altering the ported algorithm.
    df_id: pd.DataFrame = pd.DataFrame()
    while counter <= size:

        filter_value = ((df_distances['target'] == target) &
                        (df_distances['origin'] != origin) &
                        (~df_distances['origin'].isin(origins)))
        df_target = fiter_order_df(filter_value, 'distance', df_distances)

        filter_value = ((df_distances['origin'] == target) &
                        (df_distances['target'] != origin) &
                        (~df_distances['target'].isin(origins)))
        df_origin = fiter_order_df(filter_value, 'distance', df_distances)

        distance = -1
        if (len(df_origin) > 0) and (len(df_target) > 0):
            distance_between = df_origin.iloc[0]['distance'] - df_target.iloc[0]['distance']
            distance = 0 if (distance_between < 0) else 1

        if distance == -1 and len(df_target) > 0:
            distance = 1

        if distance == -1 and len(df_origin) > 0:
            distance = 2
            filter_value = df_distances['target'] == target
            df_id = df_distances[filter_value].reset_index(drop = True)

        if counter == size:
            distance = 3
            filter_value = df_distances['target'] == target
            df_id = df_distances[filter_value].reset_index(drop = True)

        match distance:
            case 0:
                data = {'origin': int(df_origin.iloc[0]['origin']),
                        'target': int(df_origin.iloc[0]['target']),
                        'distance': df_origin.iloc[0]['distance'],
                        'x': df_target.iloc[0]['x'],
                        'y': df_target.iloc[0]['y']}
                values.append(int(origin))
                values.append(int(df_origin.iloc[0]['origin']))
                values.append(int(df_origin.iloc[0]['target']))
            case 1:
                data = {'origin': df_target.iloc[0]['target'],
                        'target': df_target.iloc[0]['origin'],
                        'distance': df_target.iloc[0]['distance'],
                        'x': df_target.iloc[0]['x'],
                        'y': df_target.iloc[0]['y']}
                values.append(int(origin))
                values.append(df_target.iloc[0]['target'])
                values.append(df_target.iloc[0]['origin'])
            case 2:
                data = {'origin': int(df_origin.iloc[0]['origin']),
                        'target': int(df_origin.iloc[0]['target']),
                        'distance': df_origin.iloc[0]['distance'],
                        'x': df_id.iloc[0]['x'],
                        'y': df_id.iloc[0]['y']}
                values.append(int(origin))
                values.append(int(df_origin.iloc[0]['origin']))
                values.append(int(df_origin.iloc[0]['target']))
            case 3:
                data = {'origin': int(target),
                        'target': int(target),
                        'distance': 0,
                        'x': df_id.iloc[0]['x'],
                        'y': df_id.iloc[0]['y']}
                values.append(int(target))
                values.append(int(target))
                values.append(int(target))
            case _:
                values = []

        if len(values) > 0:
            df_order, origin, target, origins = build_route_object(
                origins, data, counter, values, df_order
            )
            values = []

        counter += 1

    return df_order.reset_index(drop = True)
