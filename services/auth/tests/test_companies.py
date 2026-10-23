'''
    Companies: what the schemas accept. Pure, so the CI runs them with no .env.
'''
import pytest
from pydantic import ValidationError

from schemas.companies import CompanyRequest, CompanyUpdateRequest


def test_a_company_needs_a_name_and_a_numeric_tax_id() -> None:
    '''The NIT is digits only; the name has the length of a user's client.'''
    company = CompanyRequest(name = 'Distribuidora Andina S.R.L.', tax_id = '1020304050')
    assert company.tax_id == '1020304050'
    with pytest.raises(ValidationError):
        CompanyRequest(name = 'Andina', tax_id = '10-20-30')
    with pytest.raises(ValidationError):
        CompanyRequest(name = 'AB')


def test_an_update_never_carries_the_name() -> None:
    '''The name is the users' client: an update only knows NIT and active.'''
    update = CompanyUpdateRequest(name = 'Otra', active = False)
    assert update.model_dump(exclude_unset = True) == {'active': False}
