'''
    The audit is the controller's: it is the one that holds the request, and
    with it the caller's token EVENTS asks for.

    On 24-oct-2026 `persist_run` and `persist_dataset` carried `@audit_event`
    too. In `services/` there is no request, so every one of those records
    went out with no token and EVENTS refused it (401), while the controller
    had already audited the same change.
'''
from services.analytics_utils import persist_run
from services.commercial_utils import persist_dataset


def test_storing_a_run_or_a_dataset_does_not_audit_on_its_own():
    '''Neither is wrapped by `audit_event`: their controllers audit them.'''
    assert not hasattr(persist_run, '__wrapped__')
    assert not hasattr(persist_dataset, '__wrapped__')
