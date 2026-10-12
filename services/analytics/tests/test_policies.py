'''
    Controller tests of the two policies the analyses are judged with: each
    answers RESOLVED —the account's own where it set one, the default
    elsewhere— and says which of the two it is running on.
'''
import asyncio

from controllers import policies
from schemas.objectives import CommercialPolicyResponse, CommercialPolicySchema
from schemas.receivables import CreditPolicyRequest, CreditPolicyResponse


def test_credit_policy_round_trip(monkeypatch):
    '''
        Writing a policy answers with the RESOLVED one, so the caller sees
        which defaults filled the gaps before a provision uses them.
    '''
    stored: dict = {}
    monkeypatch.setattr(
        policies, 'save_credit_policy',
        lambda dynamodb_resource, owner_email, policy: stored.update(policy) or stored
    )
    monkeypatch.setattr(policies, 'get_credit_policy', lambda **_: stored or None)

    response = asyncio.run(policies.save_credit_policy_controller(
        dynamodb_resource = None,
        policy = CreditPolicyRequest(financial_rate_daily = 0.002),
        request = None,
        current_user = 'tester@bearsoft.com.bo'
    ))

    assert isinstance(response, CreditPolicyResponse)
    assert response.source_code == 'CLIENT'
    assert response.financial_rate_daily == 0.002
    # What was not sent falls back to the service default.
    assert response.aging_buckets
    assert response.loss_rates


def test_the_credit_policy_controller_answers_the_resolved_policy(monkeypatch):
    '''
        The read side of the credit policy: it must show which defaults are
        in force, because a provision computed with them cannot be audited
        otherwise.
    '''
    monkeypatch.setattr(policies, 'get_credit_policy', lambda **_: None)

    response = asyncio.run(policies.get_credit_policy_controller(
        dynamodb_resource = None, request = None,
        current_user = 'tester@bearsoft.com.bo'
    ))

    assert isinstance(response, CreditPolicyResponse)
    assert response.source_code == 'DEFAULT'


def test_the_commercial_policy_round_trips_and_answers_resolved(monkeypatch):
    '''
        Saving must answer with the RESOLVED yardstick, not with what was
        sent: the caller has to see which defaults filled the gaps before a
        semaphore is drawn with them.
    '''
    stored: dict = {}
    monkeypatch.setattr(policies, 'save_commercial_policy',
                        lambda **kwargs: stored.update(kwargs['policy']))
    monkeypatch.setattr(policies, 'get_commercial_policy', lambda **_: stored)

    response = asyncio.run(policies.save_commercial_policy_controller(
        dynamodb_resource = None,
        policy = CommercialPolicySchema(
            green_from = 0.9, points_per_cluster = {'PLATINIUM': 20.0}
        ),
        request = None,
        current_user = 'tester@bearsoft.com.bo'
    ))

    assert isinstance(response, CommercialPolicyResponse)
    assert response.source_code == 'CLIENT'
    assert response.green_from == 0.9
    assert response.points_per_cluster == {'PLATINIUM': 20.0}
    # Untouched by the caller, so the default has to be showing.
    assert response.yellow_from == 0.5


def test_reading_the_commercial_policy_shows_the_defaults_in_force(monkeypatch):
    '''An account that never set one reads the service defaults.'''
    monkeypatch.setattr(policies, 'get_commercial_policy', lambda **_: None)

    response = asyncio.run(policies.get_commercial_policy_controller(
        dynamodb_resource = None, request = None,
        current_user = 'tester@bearsoft.com.bo'
    ))

    assert isinstance(response, CommercialPolicyResponse)
    assert (response.yellow_from, response.green_from) == (0.5, 1.0)


def test_an_account_without_its_own_commercial_policy_says_so(monkeypatch):
    '''With nothing stored, the policy answers DEFAULT: the views warn on it.'''
    monkeypatch.setattr(policies, 'get_commercial_policy', lambda **_: None)

    response = asyncio.run(policies.get_commercial_policy_controller(
        dynamodb_resource = None, request = None, current_user = 'tester@bearsoft.com.bo'
    ))

    assert isinstance(response, CommercialPolicyResponse)
    assert response.source_code == 'DEFAULT'
