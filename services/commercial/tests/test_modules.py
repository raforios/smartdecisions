'''
    The modules a company's data turns on: a counter-only shop has no
    analyses by client, a mixed one has them, a coordinate at zero is no
    location, and companions turn on their own modules.
'''
import pandas as pd

from schemas.modules import SalesProfile
from services.commercial import COUNTER_CLIENT
from services.modules import active_modules, sales_profile


def test_a_counter_only_shop_has_no_clients_and_a_mixed_one_has():
    '''Every sale to the counter client: no clients; one delivery to a named client: clients.'''
    counter = pd.DataFrame({'pos_name': [COUNTER_CLIENT, COUNTER_CLIENT]})
    mixed = pd.DataFrame({'pos_name': [COUNTER_CLIENT, 'Clínica Sur']})
    assert sales_profile(counter).named_clients is False
    assert sales_profile(mixed).named_clients is True
    assert sales_profile(pd.DataFrame()) == SalesProfile()


def test_credit_and_locations_come_from_the_sales():
    '''A credit sale turns credit on; a coordinate at zero is no location.'''
    frame = pd.DataFrame({'pos_name': ['A', 'B'], 'payment_terms': ['cash', 'credit'],
                          'latitude': [0, None], 'longitude': [0, -68.1]})
    profile = sales_profile(frame)
    assert profile.credit_sales is True and profile.coordinates is False
    located = frame.assign(latitude = [None, -16.5])
    assert sales_profile(located).coordinates is True


def test_companions_turn_on_their_own_modules():
    '''Stock, purchases, objectives, payments and visits attached say the rest.'''
    dataset = {'stock_s3_key': 's.csv', 'collections_s3_key': 'c.csv', 'visits_s3_key': 'v.csv'}
    modules = active_modules(dataset, SalesProfile())
    assert (modules.stock, modules.receivables, modules.routes) == (True, True, True)
    assert (modules.purchases, modules.objectives, modules.clients) == (False, False, False)
