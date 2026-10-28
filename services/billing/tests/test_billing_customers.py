'''
    Tests for the shop's customers.

    What they protect: an invoice creates its buyer as a customer and only
    fills what a known customer lacked, so a correction is never undone; a
    correction replaces what it carries and keeps the rest; and one shop never
    reads another's customers.
'''
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from controllers import billing_customers as controllers
from schemas.billing import BillingError, Buyer
from schemas.billing_customers import CustomerEdit, CustomerOut, CustomersResponse
from services import billing_customers, utils
from services.exceptions import RegisterNotFoundError
from tests.test_billing import CASHIER, OTHER_OWNER, OWNER, _dynamodb # pylint: disable=unused-import

MANAGER = 'gerente@farmacia.bo'


def test_an_unknown_buyer_becomes_a_customer(dynamodb):
    '''
        The first invoice to a NIT creates the customer with what it carried.
    '''
    billing_customers.remember_customer(dynamodb, OWNER, Buyer(
        name = 'Ana Quispe', document = ' 4567890 ', document_type = 1,
        email = 'ana@correo.bo'
    ), CASHIER)

    customer = billing_customers.get_customer(dynamodb, OWNER, '4567890')

    assert (customer.name, customer.document_type, customer.email) == \
        ('Ana Quispe', 1, 'ana@correo.bo')
    assert customer.created_by == CASHIER
    assert customer.last_invoiced_at


def test_a_known_customer_only_gets_what_it_lacked(dynamodb):
    '''
        A later invoice fills the empty email and leaves the name alone, even
        when the cashier typed it differently.
    '''
    billing_customers.remember_customer(dynamodb, OWNER, Buyer(
        name = 'Ana Quispe', document = '4567890', document_type = 1
    ), CASHIER)
    first = billing_customers.get_customer(dynamodb, OWNER, '4567890')

    billing_customers.remember_customer(dynamodb, OWNER, Buyer(
        name = 'ANA Q.', document = '4567890', document_type = 1, email = 'ana@correo.bo'
    ), 'otra@farmacia.bo')
    second = billing_customers.get_customer(dynamodb, OWNER, '4567890')

    assert (second.name, second.email) == ('Ana Quispe', 'ana@correo.bo')
    assert (second.created_at, second.created_by) == (first.created_at, CASHIER)


def test_a_correction_replaces_what_it_carries_and_an_invoice_does_not_undo_it(dynamodb):
    '''
        Overwriting is the explicit act; the next invoice only fills gaps.
    '''
    billing_customers.remember_customer(dynamodb, OWNER, Buyer(
        name = 'Ana Quispe', document = '4567890', document_type = 1,
        email = 'vieja@correo.bo'
    ), CASHIER)

    corrected = billing_customers.update_customer(dynamodb, OWNER, CustomerEdit(
        document = '4567890', email = 'nueva@correo.bo'
    ), MANAGER)
    billing_customers.remember_customer(dynamodb, OWNER, Buyer(
        document = '4567890', email = 'vieja@correo.bo'
    ), CASHIER)

    stored = billing_customers.get_customer(dynamodb, OWNER, '4567890')
    assert (corrected.name, corrected.email, corrected.updated_by) == \
        ('Ana Quispe', 'nueva@correo.bo', MANAGER)
    assert stored.email == 'nueva@correo.bo'


def test_one_shop_never_reads_anothers_customers(dynamodb):
    '''
        Another shop's customer answers exactly like one that does not exist.
    '''
    billing_customers.remember_customer(dynamodb, OWNER, Buyer(document = '4567890'), CASHIER)

    with pytest.raises(RegisterNotFoundError) as missing:
        billing_customers.get_customer(dynamodb, OTHER_OWNER, '4567890')

    assert missing.value.detail == BillingError.CUSTOMER_NOT_FOUND.value
    assert billing_customers.list_customers(dynamodb, OTHER_OWNER).total == 0
    assert billing_customers.list_customers(dynamodb, OWNER).total == 1


def test_the_customer_controllers_return_their_models(dynamodb):
    '''
        Each endpoint returns its model assembled; only the correction is
        audited.
    '''
    billing_customers.remember_customer(dynamodb, OWNER, Buyer(document = '4567890'), CASHIER)
    audited = []

    def _record(
        result, # pylint: disable=unused-argument
        kwargs, # pylint: disable=unused-argument
        spec
    ):
        audited.append((spec.entity_name, spec.action))
        return {}

    common = {'dynamodb_resource': dynamodb, 'owner': OWNER, 'request': None,
              'current_user': MANAGER}
    with patch.object(utils, '_audit_payload', _record), \
            patch.object(utils, 'send_audit_event', AsyncMock()):
        listed = asyncio.run(controllers.list_customers_controller(**common))
        one = asyncio.run(controllers.get_customer_controller(document = '4567890', **common))
        edited = asyncio.run(controllers.update_customer_controller(
            edit = CustomerEdit(document = '4567890', name = 'Ana Quispe'), **common
        ))

    assert isinstance(listed, CustomersResponse)
    assert isinstance(one, CustomerOut)
    assert edited.name == 'Ana Quispe'
    assert audited == [('Customer', 'UPDATE')]
