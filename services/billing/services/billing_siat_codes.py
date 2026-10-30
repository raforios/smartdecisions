'''
    The codes and catalogues a shop needs from the SIN before it invoices.

    Both are stored in `billing_settings`, beside the shop's configuration,
    because they are the same kind of thing: per-tenant values read and
    written by the same owner. A CUIS is asked for once a year and a CUFD once
    a day; asking the tax office on every invoice would make each sale wait on
    a service we do not control.

    The CUFDs replaced in the last days are kept beside the one in force:
    manual contingency invoices are transcribed with the CUFD that was in
    force when the contingency began, which may have been replaced since.

    | setting_key                          | What                         |
    |--------------------------------------|------------------------------|
    | siat#codes#<branch>#<point_of_sale>  | CUIS and CUFD in force, and  |
    |                                      | the CUFDs of the last days   |
    | siat#catalog#<catalogue>             | One synchronised catalogue   |
'''
from datetime import datetime, timedelta
from typing import Any, Final

from boto3.resources.base import ServiceResource

from models.billing import OWNER_KEY, SETTINGS_TABLE, SETTING_SORT_KEY
from schemas.billing import BillingError
from schemas.billing_siat import (
    CatalogOut,
    CatalogSummary,
    CatalogsSyncResponse,
    SiatCatalog,
    SiatCodesOut
)
from services import billing_siat_client as siat_client
from services.billing import from_dynamo, get_settings, now_iso, write_item
from services.billing_siat_client import Emitter
from services.exceptions import InvalidInputError, RegisterNotFoundError
from services.logger_config import custom_logger as logger
from services.utils import get_current_time_gmt, load_parameters

CODES_PREFIX = 'siat#codes#'
CATALOG_PREFIX = 'siat#catalog#'

# How long the norm stretches a CUFD when the SIN cannot issue the next one.
CUFD_STRETCH_HOURS: Final[int] = 72

PARAMETERS = load_parameters({'BILLING_CUFD_HISTORY_DAYS': int})

# The fields of one CUFD, kept together in the history.
_CUFD_FIELDS: Final[tuple[str, ...]] = ('cufd', 'control_code', 'cufd_valid_until', 'address',
                                        'cufd_obtained_at')


def emitter_for(
    dynamodb_resource: ServiceResource,
    owner: str
) -> Emitter:
    '''
        Who issues, as the shop's settings say.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.

        Returns:
            Emitter: Its NIT, branch and point of sale.

        Raises:
            RegisterNotFoundError: The shop has not been set up.
            InvalidInputError: The shop has no NIT, and nothing can be asked
                of the tax office without one.
    '''
    settings = get_settings(dynamodb_resource, owner)
    if not settings.document:
        raise InvalidInputError(detail = BillingError.SIAT_ISSUER_INCOMPLETE.value)
    return Emitter(nit = settings.document, branch = settings.branch,
                   point_of_sale = settings.point_of_sale)


def _codes_key(emitter: Emitter) -> str:
    '''
        Where the codes of one branch and point of sale are stored.

        Args:
            emitter (Emitter): Who is issuing.

        Returns:
            str: The setting key.
    '''
    return f'{CODES_PREFIX}{emitter.branch}#{emitter.point_of_sale or 0}'


def _moment(stamp: str) -> datetime:
    '''
        A timestamp as the SIAT writes it, in the service's zone when it has
        none.

        Args:
            stamp (str): ISO 8601.

        Returns:
            datetime: Aware of its zone.
    '''
    moment = datetime.fromisoformat(stamp)
    # The SIAT stamps its validity with the Bolivian offset; one without it is
    # read in the same zone rather than refused.
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo = get_current_time_gmt().tzinfo)
    return moment


def _expired(valid_until: str | None) -> bool:
    '''
        Whether a code is missing or past its validity.

        Args:
            valid_until (str | None): As the SIAT returned it.

        Returns:
            bool: True when it has to be asked for again.
    '''
    return not valid_until or _moment(valid_until) <= get_current_time_gmt()


def current_codes(
    dynamodb_resource: ServiceResource,
    owner: str,
    force_cufd: bool = False
) -> SiatCodesOut:
    '''
        The CUIS and CUFD in force, asking the tax office only for the ones
        that are missing or expired.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            force_cufd (bool): Ask for a new CUFD even if one is in force —
                what the SIN asks for before registering a significant event.

        Returns:
            SiatCodesOut: The codes in force.

        Raises:
            ServiceUnavailableError: The SIAT is unreachable.
            InvalidInputError: The tax office refused, or the shop has no NIT.
    '''
    emitter = emitter_for(dynamodb_resource, owner)
    key = _codes_key(emitter)
    stored = _stored(dynamodb_resource, owner, key)
    previous = _cufd_entry(stored)

    renewed = False
    if _expired(stored.get('cuis_valid_until')):
        cuis = siat_client.request_cuis(emitter)
        stored.update(cuis = cuis.cuis, cuis_valid_until = cuis.valid_until, cufd = None)
        renewed = True
    if force_cufd or _expired(stored.get('cufd_valid_until')) or not stored.get('cufd'):
        cufd = siat_client.request_cufd(emitter, stored['cuis'])
        stored.update(cufd = cufd.cufd, control_code = cufd.control_code,
                      cufd_valid_until = cufd.valid_until, address = cufd.address,
                      cufd_obtained_at = now_iso(),
                      cufd_history = _recent(stored.get('cufd_history', []) + previous))
        renewed = True

    codes = _codes_out(emitter, stored)
    if renewed:
        write_item(dynamodb_resource, SETTINGS_TABLE, {
            OWNER_KEY: owner, SETTING_SORT_KEY: key, **codes.model_dump(),
            'cufd_obtained_at': stored.get('cufd_obtained_at'),
            'cufd_history': stored.get('cufd_history', []), 'updated_at': now_iso()
        })
        message = f'SIAT codes renewed for {owner} at {key}.'
        logger.info(message)
    return codes


def last_codes(
    dynamodb_resource: ServiceResource,
    owner: str
) -> SiatCodesOut | None:
    '''
        The codes last stored, without asking the tax office — what an offline
        invoice is issued with when the SIN cannot give a new CUFD.

        The norm stretches a CUFD to 72 hours when the SIN cannot issue the
        next one; past that, there is nothing to issue with.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.

        Returns:
            SiatCodesOut | None: The codes, or None when there are none usable.
    '''
    emitter = emitter_for(dynamodb_resource, owner)
    stored = _stored(dynamodb_resource, owner, _codes_key(emitter))
    if not stored.get('cufd') or not stored.get('cufd_valid_until'):
        return None
    stretched = (_moment(stored['cufd_valid_until'])
                 + timedelta(hours = CUFD_STRETCH_HOURS)).isoformat()
    return None if _expired(stretched) else _codes_out(emitter, stored)


def codes_at(
    dynamodb_resource: ServiceResource,
    owner: str,
    moment: str
) -> SiatCodesOut | None:
    '''
        The codes as they were at a past moment: the CUIS in force and the
        CUFD the shop was issuing with then — the latest obtained before it.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            moment (str): ISO 8601, with its offset.

        Returns:
            SiatCodesOut | None: The codes, or None when no CUFD kept covers
                that moment.
    '''
    emitter = emitter_for(dynamodb_resource, owner)
    stored = _stored(dynamodb_resource, owner, _codes_key(emitter))
    when = _moment(moment)
    earlier = [entry for entry in stored.get('cufd_history', []) + _cufd_entry(stored)
               if entry.get('cufd_obtained_at') and _moment(entry['cufd_obtained_at']) <= when]
    if not earlier:
        return None
    entry = max(earlier, key = lambda one: _moment(one['cufd_obtained_at']))
    if when > _moment(entry['cufd_valid_until']) + timedelta(hours = CUFD_STRETCH_HOURS):
        return None
    return _codes_out(emitter, {**stored, **entry})


def _cufd_entry(stored: dict[str, Any]) -> list[dict[str, Any]]:
    '''
        The CUFD of a codes item, as one history entry; none when it has
        no CUFD.
    '''
    return [{field: stored.get(field) for field in _CUFD_FIELDS}] if stored.get('cufd') else []


def _recent(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    '''
        The history entries obtained within the days kept; one with no
        obtaining moment, stored before the history existed, is dropped.
    '''
    since = get_current_time_gmt() - timedelta(days = PARAMETERS['BILLING_CUFD_HISTORY_DAYS'])
    return [entry for entry in history
            if entry.get('cufd_obtained_at') and _moment(entry['cufd_obtained_at']) >= since]


def _stored(
    dynamodb_resource: ServiceResource,
    owner: str,
    key: str
) -> dict[str, Any]:
    '''
        The codes item, or an empty one.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            key (str): Its setting key.

        Returns:
            dict[str, Any]: The stored fields.
    '''
    return from_dynamo(dynamodb_resource.Table(SETTINGS_TABLE).get_item(
        Key = {OWNER_KEY: owner, SETTING_SORT_KEY: key}
    ).get('Item')) or {}


def _codes_out(
    emitter: Emitter,
    stored: dict[str, Any]
) -> SiatCodesOut:
    '''
        The stored codes as the DTO.

        Args:
            emitter (Emitter): Who is issuing.
            stored (dict[str, Any]): The codes item.

        Returns:
            SiatCodesOut: The codes.
    '''
    return SiatCodesOut(branch = emitter.branch, point_of_sale = emitter.point_of_sale or 0,
                        **{field: stored[field] for field in (
                            'cuis', 'cuis_valid_until', 'cufd', 'control_code',
                            'cufd_valid_until', 'address')})


def sync_catalogs(
    dynamodb_resource: ServiceResource,
    owner: str
) -> CatalogsSyncResponse:
    '''
        Brings every catalogue from the tax office and stores it.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.

        Returns:
            CatalogsSyncResponse: How many rows each catalogue brought.

        Raises:
            ServiceUnavailableError: The SIAT is unreachable.
            InvalidInputError: The tax office refused, or the shop has no NIT.
    '''
    emitter = emitter_for(dynamodb_resource, owner)
    cuis = current_codes(dynamodb_resource, owner).cuis
    synced_at = now_iso()
    summaries: list[CatalogSummary] = []
    for catalog in SiatCatalog:
        entries = siat_client.sync_catalog(emitter, cuis, catalog)
        write_item(dynamodb_resource, SETTINGS_TABLE, {
            OWNER_KEY: owner, SETTING_SORT_KEY: f'{CATALOG_PREFIX}{catalog.name}',
            **CatalogOut(catalog = catalog, synced_at = synced_at,
                         entries = entries).model_dump(mode = 'json')
        })
        summaries.append(CatalogSummary(catalog = catalog, entries = len(entries)))

    message = f'{len(summaries)} SIAT catalogue(s) synchronised for {owner}.'
    logger.info(message)
    return CatalogsSyncResponse(synced_at = synced_at, catalogs = summaries)


def get_catalog(
    dynamodb_resource: ServiceResource,
    owner: str,
    catalog: SiatCatalog
) -> CatalogOut:
    '''
        One stored catalogue.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            catalog (SiatCatalog): Which catalogue.

        Returns:
            CatalogOut: The catalogue as last synchronised.

        Raises:
            RegisterNotFoundError: It has never been synchronised.
    '''
    stored = from_dynamo(dynamodb_resource.Table(SETTINGS_TABLE).get_item(
        Key = {OWNER_KEY: owner, SETTING_SORT_KEY: f'{CATALOG_PREFIX}{catalog.name}'}
    ).get('Item'))
    if not stored:
        raise RegisterNotFoundError(detail = BillingError.CATALOG_NOT_SYNCED.value)
    return CatalogOut(catalog = stored['catalog'], synced_at = stored['synced_at'],
                      entries = stored['entries'])
