'''
    What every BILLING test needs before anything is imported: its business
    values, loaded in memory from the `billing` rows of docs/parametros.md
    (the rows the real table is seeded from), with no AWS and no simulated
    table.
'''
import importlib.util
from pathlib import Path


_DOCUMENT_READER = (Path(__file__).resolve().parents[3] / 'tools' / 'seeds'
                    / 'parameters_document.py')
_SPEC = importlib.util.spec_from_file_location('parameters_document', _DOCUMENT_READER)
_DOCUMENT = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_DOCUMENT)

# The business values live in the service's parameters table. The tests load
# the same rows in memory, from docs/parametros.md, before any module reads
# them on import: no AWS and no simulated table. That is why the service's
# modules are imported here, after the values, and not with the others.
# pylint: disable=wrong-import-position,ungrouped-imports
from services import utils as _utils  # noqa: E402

_utils._SERVICE_PARAMETERS.update(_DOCUMENT.values('billing'))  # pylint: disable=protected-access


# pylint: enable=wrong-import-position,ungrouped-imports
