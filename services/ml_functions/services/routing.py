'''
    Routing calculations every service may ask for by HTTP (moved from
    COMMERCIAL on 24-oct-2026; Rafael, 21-oct: the route algorithm belongs to
    ML_FUNCTIONS). Implemented here because the libraries that provide them
    (osmnx, networkx, scikit-learn, OR-Tools) do not fit in the Lambda.

      - Clusters: k-means over (lat, lon), then evened out so no group carries
        the whole city. Plain k-means optimises compactness only, which on real
        client geography produced days of 8 and 97 stops.
      - Order: nearest neighbour, then 2-opt over the great-circle distances.
        The greedy tour alone leaves crossings; 2-opt removes them by reversing
        any segment that shortens the path. The path is OPEN: it starts at the
        first stop and ends at the last, nobody drives back.

    Pure Python and numpy, free of the environment: the CI runs this service's
    tests with no .env.
'''
from dataclasses import dataclass

import numpy as np

# A physical constant, not a decision.
EARTH_RADIUS_M: float = 6_371_000.0
# Below this a reversal does not count as a gain: it is rounding noise.
_GAIN_TOLERANCE_M: float = 1e-9


@dataclass(frozen = True)
class ClusterSpec:
    '''
        How the points are grouped: how many groups, the seed that makes the
        grouping reproducible and the iterations k-means may take.
    '''
    clusters: int
    seed: int
    iterations: int


def haversine_matrix(points: np.ndarray) -> np.ndarray:
    '''
        Great-circle distance in metres between every pair of points.

        Args:
            points (np.ndarray): Shape (n, 2), (lat, lon) in degrees.

        Returns:
            np.ndarray: Symmetric (n, n) matrix in metres.
    '''
    radians = np.radians(points)
    lat = radians[:, 0][:, None]
    lon = radians[:, 1][:, None]
    inner = (np.sin((lat - lat.T) / 2) ** 2
             + np.cos(lat) * np.cos(lat.T) * np.sin((lon - lon.T) / 2) ** 2)
    return 2 * EARTH_RADIUS_M * np.arcsin(np.sqrt(np.clip(inner, 0, 1)))


def _kmeans(
    points: np.ndarray,
    spec: ClusterSpec
) -> np.ndarray:
    '''
        Lloyd's k-means: the group of each point.
    '''
    count = len(points)
    if spec.clusters <= 1 or count <= spec.clusters:
        return np.arange(count) % max(spec.clusters, 1)

    rng = np.random.default_rng(spec.seed)
    centroids = points[rng.choice(count, size = spec.clusters, replace = False)]
    labels = np.zeros(count, dtype = int)
    for _ in range(spec.iterations):
        distances = np.linalg.norm(points[:, None, :] - centroids[None, :, :], axis = 2)
        updated = distances.argmin(axis = 1)
        if np.array_equal(updated, labels):
            break
        labels = updated
        for index in range(spec.clusters):
            member = points[labels == index]
            if len(member):
                centroids[index] = member.mean(axis = 0)
    return labels


def _balance(
    points: np.ndarray,
    labels: np.ndarray,
    clusters: int
) -> np.ndarray:
    '''
        Hands the points furthest from their own centroid to the nearest group
        that still has room, until no group passes an even share.
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
                room = [index for index in range(clusters)
                        if index != source and filled[index] < capacity]
                if not room:
                    break
                distances = np.linalg.norm(centroids[room] - points[member], axis = 1)
                labels[member] = room[int(np.argmin(distances))]
    return labels


def cluster_points(
    points: list[list[float]],
    spec: ClusterSpec
) -> list[int]:
    '''
        Splits the points into `spec.clusters` compact groups of even size.

        Args:
            points (list[list[float]]): (lat, lon) of each point.
            spec (ClusterSpec): Groups, seed and iterations.

        Returns:
            list[int]: The group of each point (0-based), in input order.
    '''
    coordinates = np.array(points, dtype = float)
    if spec.clusters <= 1:
        return [0] * len(points)
    labels = _balance(coordinates, _kmeans(coordinates, spec), spec.clusters)
    return [int(label) for label in labels]


def _nearest_neighbour(distances: np.ndarray) -> list[int]:
    '''
        A first tour that always hops to the closest stop not yet visited.
    '''
    unvisited = set(range(1, len(distances)))
    tour = [0]
    while unvisited:
        current = tour[-1]
        nearest = min(unvisited, key = lambda index: distances[current][index])
        tour.append(nearest)
        unvisited.remove(nearest)
    return tour


def _two_opt(
    tour: list[int],
    distances: np.ndarray,
    passes: int
) -> list[int]:
    '''
        Reverses every segment whose reversal shortens the open path.
    '''
    best = tour[:]
    for _ in range(passes):
        improved = False
        for first in range(1, len(best) - 1):
            for second in range(first + 1, len(best) - 1):
                before, start = best[first - 1], best[first]
                end, after = best[second], best[second + 1]
                current = distances[before][start] + distances[end][after]
                swapped = distances[before][end] + distances[start][after]
                if swapped < current - _GAIN_TOLERANCE_M:
                    best[first:second + 1] = reversed(best[first:second + 1])
                    improved = True
        if not improved:
            break
    return best


def order_points(
    points: list[list[float]],
    passes: int
) -> list[int]:
    '''
        The visit order of the points, starting at the first one.

        Args:
            points (list[list[float]]): (lat, lon) of each stop.
            passes (int): Most 2-opt passes; it stops earlier when one finds
                nothing to improve.

        Returns:
            list[int]: Indices into `points`, in visit order.
    '''
    if len(points) <= 2:
        return list(range(len(points)))
    distances = haversine_matrix(np.array(points, dtype = float))
    return _two_opt(_nearest_neighbour(distances), distances, passes)
