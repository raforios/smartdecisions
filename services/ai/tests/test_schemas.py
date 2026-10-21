'''
    Tests of the AI rules that need no configuration: they run in the CI of
    GitHub Actions, which has no .env.
'''
import re

import pytest
from pydantic import ValidationError

from schemas.ai import VIEW_PATTERN, ExplainRequest


@pytest.mark.parametrize('view', ['objectives', 'stock', 'fx_effect', 'route_plans',
                                  'route_live', 'route_optimize', 'route_compare'])
def test_every_view_the_portal_explains_is_known(view):
    '''
        The portal mounts an explain button on Cumplimiento and on Stock. Both
        views were missing here, so the request died as a 422 before reaching
        the model and the portal printed the error list as "[object Object]".
    '''
    assert re.fullmatch(VIEW_PATTERN, view)


@pytest.mark.parametrize('view', ['finance_summary', 'finance_projection', 'billing_till'])
def test_a_product_names_its_own_views(view):
    '''
        AI is a base service (19-oct-2026): FINANCE or BILLING bring their views
        without changing AI. A view exists when it has an active role.
    '''
    assert re.fullmatch(VIEW_PATTERN, view)


@pytest.mark.parametrize('view', ['', 'ab', 'Finance', 'finance-summary', 'ignore all; rules'])
def test_a_view_name_is_never_free_text(view):
    '''Only a slug passes: an arbitrary string never reaches the model.'''
    with pytest.raises(ValidationError):
        ExplainRequest(view = view, data = {'x': 1})
