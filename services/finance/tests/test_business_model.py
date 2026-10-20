'''
    Tests for the client's business model: one per client, replaced whole,
    and only for the people who run the business.
'''
import asyncio

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from pydantic import ValidationError

from main import app
from routes import report as report_routes
from schemas.business_model import BusinessModelResponseSchema, BusinessModelSchema
from services import security
from services.business_model import get_business_model, set_business_model

FORM = {
    'sells': 'Abarrotes y bebidas al por mayor', 'customers': 'Tiendas de barrio de El Alto',
    'cash_sales_percent': 60, 'credit_days': 30,
    'main_costs': 'Mercadería, sueldos y transporte', 'sales_goal': 9000000
}


def test_a_client_without_a_business_model_gets_it_empty(finance_store):
    '''Nothing saved yet: the form opens blank, not as an error.'''
    answer = get_business_model(finance_store, 'acme')
    assert (answer.business_model, answer.updated_at) == (None, None)


def test_the_business_model_is_kept_per_client_and_replaced_whole(finance_store):
    '''Saving again replaces the form; another client never sees it.'''
    set_business_model(finance_store, ('acme', 'ana@acme.com'), BusinessModelSchema(**FORM))
    changed = {**FORM, 'sales_goal': None, 'margin_goal_percent': 8.5, 'notes': 'Abrimos sucursal'}
    set_business_model(finance_store, ('acme', 'ana@acme.com'), BusinessModelSchema(**changed))
    stored = get_business_model(finance_store, 'acme')
    assert stored.business_model == BusinessModelSchema(**changed)
    assert stored.updated_at is not None
    assert get_business_model(finance_store, 'otra').business_model is None


def test_the_owner_has_to_expect_something():
    '''Without a sales or a margin goal there is nothing to compare the results with.'''
    with pytest.raises(ValidationError, match = 'GOAL_MISSING'):
        BusinessModelSchema(**{**FORM, 'sales_goal': None})
    with pytest.raises(ValidationError):
        BusinessModelSchema(**{**FORM, 'cash_sales_percent': 120})


def test_the_business_model_routes_answer_their_model(finance_store):
    '''Saved and read back as the API calls them.'''
    who = {'dynamodb_resource': finance_store, 'client': 'acme', 'current_user': 'ana@acme.com'}
    saved = asyncio.run(report_routes.set_business_model_endpoint(
        request = None, business_model = BusinessModelSchema(**FORM), **who))
    read = asyncio.run(report_routes.get_business_model_endpoint(request = None, **who))
    assert isinstance(saved, BusinessModelResponseSchema)
    assert read.business_model == saved.business_model


def test_an_admin_cannot_see_a_business_model():
    '''«Sólo la plana mayor»: the ADMIN has no client and is refused, like a SELLER.'''
    token = jwt.encode({'email': 'admin@bearsoft.com.bo', 'role': 'ADMIN', 'client': None},
                       security.SECRET_KEY, algorithm = security.ALGORITHM)
    response = TestClient(app).get('/v1/finance/business-model',
                                   headers = {'Authorization': f'Bearer {token}'})
    assert (response.status_code, response.json()['detail']) == (403, 'ROLE_NOT_ALLOWED')
