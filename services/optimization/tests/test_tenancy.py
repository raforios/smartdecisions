'''
    Tests for client isolation in the routes table.

    The partition of this table is deleted before every upload, so a key shared
    between two clients does not merely leak data — the second upload erases the
    first client's points. That makes the key itself the isolation boundary, and
    the reason these assertions live apart from the controller tests: they are
    about the shape of the key, not about an endpoint.
'''
from services import optimization_utils


def _build(owner: str, route_id: int, day: int) -> str:
    '''
        Builds a partition key.

        Args:
            owner (str): Owner of the plan.
            route_id (int): Identifier of the planned route.
            day (int): Day index within the plan.

        Returns:
            str: The partition key the table uses.
    '''
    return optimization_utils._build_route_day_key( # pylint: disable=protected-access
        owner, route_id, day
    )


def test_two_clients_planning_the_same_route_do_not_share_a_partition():
    '''
        "Route 1, day 1" must be a different partition for each client.

        Route identifiers are small integers that everybody uses, so the
        collision is the normal case and not an edge one.
    '''
    mine = _build('yo@miempresa.com', 1, 1)
    theirs = _build('otra@empresa.com', 1, 1)

    assert mine != theirs
    assert mine.startswith('yo@miempresa.com#')
    assert mine.endswith('#1#1')


def test_the_same_client_keeps_one_partition_per_route_and_day():
    '''
        Within one client the key must still separate routes and days, or
        re-uploading day 2 would wipe day 1.
    '''
    keys = {_build('yo@miempresa.com', route, day)
            for route in (1, 2) for day in (1, 2)}

    assert len(keys) == 4


def test_the_key_is_stable_for_the_same_inputs():
    '''
        The key is rebuilt on every read and every write, never stored and
        reused, so the two have to agree byte for byte.
    '''
    assert _build('yo@miempresa.com', 3, 2) == _build('yo@miempresa.com', 3, 2)
    # Numbers arriving as strings from a CSV must land on the same partition.
    assert _build('yo@miempresa.com', 3, 2) == _build('yo@miempresa.com', '3', '2')
