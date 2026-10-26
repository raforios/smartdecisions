'''
    What every COMMERCIAL test needs before anything is imported.

    1. Its business values. They live in the service's parameters table
       (`commercial_parameters`) and the modules read them on import; here
       the table is created in moto and seeded from the `commercial` rows of
       `docs/parametros.md`, the same rows the real table is seeded from, so
       the tests read the values the service reads and never AWS. moto is
       stopped once the tests are collected: by then every module has its
       values.
    2. ML_FUNCTIONS: every calculation COMMERCIAL asks for by HTTP is
       answered by ML_FUNCTIONS' own pure modules, loaded from their files, so
       the tests run the one copy of each formula and never the network.
       Only the ML_FUNCTIONS paths are answered here: any other call (EVENTS,
       FILES) goes on to whatever `requests.post` was, as it did before. A
       test that needs to see what was asked, or to make the call fail,
       patches `requests.post` itself.
'''
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import boto3
import pytest
from moto import mock_aws

from services.environment import load_and_validate_env_vars

_SERVICES = Path(__file__).resolve().parents[2]
_ML_SERVICES = _SERVICES / 'ml_functions' / 'services'
_DOCUMENT_READER = _SERVICES.parent / 'tools' / 'seeds' / 'parameters_document.py'


def _load(
    name: str,
    path: Path
) -> ModuleType:
    '''
        A module from outside this service, under a name that cannot clash
        with this service's own `services` package.
    '''
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_PARAMETERS_MOCK = mock_aws()
_PARAMETERS_MOCK.start()
_load('parameters_document', _DOCUMENT_READER).create_and_seed(
    boto3.resource('dynamodb', region_name = 'us-east-1'),
    load_and_validate_env_vars({'DYNAMODB_TABLE_NAME_SERVICE_PARAMETERS': str})[
        'DYNAMODB_TABLE_NAME_SERVICE_PARAMETERS'],
    'commercial')

# The services are imported only once moto holds their parameters table, so
# they cannot be grouped with the environment reader above.
# pylint: disable=wrong-import-position,ungrouped-imports
from services import calculations  # noqa: E402
from services.utils import load_parameters  # noqa: E402
# pylint: enable=wrong-import-position,ungrouped-imports

# Every value is read now, while moto holds the table.
load_parameters({})

_CLASSIFICATION = _load('ml_functions_classification', _ML_SERVICES / 'classification.py')
ML_ROUTING = _load('ml_functions_routing', _ML_SERVICES / 'routing.py')


def pytest_collection_finish(session: pytest.Session) -> None:  # pylint: disable=unused-argument
    '''
        Every module read its values while the tests were collected: moto
        stops here, so each test starts its own as it always did.
    '''
    _PARAMETERS_MOCK.stop()


class Answer:  # pylint: disable=too-few-public-methods
    '''What `requests.post` returns: ok and a JSON body.'''

    def __init__(
        self,
        body: dict[str, Any]
    ) -> None:
        self.ok = True
        self.status_code = 200
        self.text = ''
        self._body = body

    def json(self) -> dict[str, Any]:
        '''The body.'''
        return self._body


def _rules(body: dict[str, Any]) -> dict[str, Any]:
    '''The association rules, shaped as the endpoint answers them.'''
    rules = _CLASSIFICATION.association_rules(body['transactions'], body['min_support'],
                                              body['min_lift'])
    return {'transactions': len(body['transactions']),
            'rules': [{'antecedents': list(rule.antecedents),
                       'consequents': list(rule.consequents), 'support': rule.support,
                       'confidence': rule.confidence, 'lift': rule.lift} for rule in rules]}


def answer_like_ml_functions(
    url: str,
    json: dict[str, Any]
) -> Answer | None:
    '''
        Answers one request the way ML_FUNCTIONS does.

        Args:
            url (str): The endpoint asked.
            json (dict[str, Any]): The request body.

        Returns:
            Answer | None: The response; None when the URL is not ML_FUNCTIONS'.
    '''
    if url.endswith('/v1/classification/tiers'):
        return Answer({'tiers': _CLASSIFICATION.rank_tiers(json['values'], json['cuts'])})
    if url.endswith('/v1/classification/association-rules'):
        return Answer(_rules(json))
    if url.endswith('/v1/routing/clusters'):
        spec = ML_ROUTING.ClusterSpec(clusters = json['clusters'], seed = json['seed'],
                                    iterations = json['iterations'])
        return Answer({'labels': ML_ROUTING.cluster_points(json['points'], spec)})
    if url.endswith('/v1/routing/order'):
        return Answer({'order': ML_ROUTING.order_points(json['points'], json['passes'])})
    return None


@pytest.fixture(autouse = True)
def _ml_functions(monkeypatch: pytest.MonkeyPatch) -> None:
    '''
        Every test answers its ML_FUNCTIONS calls with ML_FUNCTIONS' code.
    '''
    original = calculations.requests.post

    def _post(
        url: str,
        json: dict[str, Any] | None = None,
        timeout: float | None = None,
        **kwargs: Any
    ) -> Any:
        answer = answer_like_ml_functions(url, json or {})
        if answer is not None:
            return answer
        return original(url, json = json, timeout = timeout, **kwargs)

    monkeypatch.setattr(calculations.requests, 'post', _post)
