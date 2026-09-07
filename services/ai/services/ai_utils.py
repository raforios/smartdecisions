'''
    DynamoDB access for the AI interpretation service.

    Two stores with opposite lifetimes: the roles are meant to last and be
    versioned, the answers are meant to expire. Keeping their access here means
    the domain module reasons about explanations and never about tables.
'''
import hashlib
import json
from typing import Any, Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from models.ai import (
    CACHE_PARTITION_KEY,
    PROMPTS_PARTITION_KEY,
    ExplanationItem,
    PromptItem
)
from schemas.ai import AIError
from services.environment import load_and_validate_env_vars
from services.exceptions import ServiceUnavailableError
from services.logger_config import custom_logger as logger


ENV_VARS = load_and_validate_env_vars({
    'DYNAMODB_TABLE_NAME_AI_PROMPTS': str,
    'DYNAMODB_TABLE_NAME_AI_EXPLANATIONS': str,
})
PROMPTS_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_AI_PROMPTS']
CACHE_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_AI_EXPLANATIONS']

# Region and credentials come from the default chain (Lambda role in AWS).
_resource = boto3.resource('dynamodb')


def _table(name: str):
    '''
        Returns a table handle.

        Args:
            name (str): Table name.

        Returns:
            Any: The boto3 table resource.
    '''
    return _resource.Table(name)


def build_cache_key(view: str, payload: Dict[str, Any], prompt_version: int) -> str:
    '''
        Builds the key an answer is stored under.

        The three inputs travel together because changing any of them changes
        the answer: a different view, different figures, or a retuned role. That
        is also what makes retuning safe — a new version simply stops hitting
        what the old one cached, with nothing to delete.

        The payload is serialised with sorted keys so two identical screens
        produce the same key regardless of dictionary order.

        Args:
            view (str): View being explained.
            payload (Dict[str, Any]): Validated view payload.
            prompt_version (int): Version of the role in force.

        Returns:
            str: Hexadecimal SHA-256 of the three.
    '''
    material = json.dumps(
        {'view': view, 'payload': payload, 'version': prompt_version},
        sort_keys = True,
        default = str
    )
    return hashlib.sha256(material.encode('utf-8')).hexdigest()


def get_active_prompt(view: str) -> Optional[PromptItem]:
    '''
        Returns the role in force for a view.

        Reads the partition backwards so the newest version comes first, and
        takes the newest one marked active: that is what makes a rollback a
        matter of flipping `active` rather than deleting anything.

        Args:
            view (str): View to look up.

        Returns:
            PromptItem | None: The active role, or None when none is configured.

        Raises:
            ServiceUnavailableError: If the table cannot be read.
    '''
    try:
        response = _table(PROMPTS_TABLE).query(
            KeyConditionExpression = Key(PROMPTS_PARTITION_KEY).eq(view),
            ScanIndexForward = False
        )
    except ClientError as error:
        error_msg = f'Failed to read the role of {view}: {error}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(detail = AIError.ROLE_NOT_CONFIGURED.value) from error

    for item in response.get('Items', []):
        prompt = PromptItem.from_item(item)
        if prompt.active:
            return prompt
    return None


def list_prompts() -> List[PromptItem]:
    '''
        Returns every configured role, so they can be reviewed.

        Returns:
            List[PromptItem]: All stored roles.

        Raises:
            ServiceUnavailableError: If the table cannot be read.
    '''
    items: List[Dict[str, Any]] = []
    kwargs: Dict[str, Any] = {}
    try:
        while True:
            response = _table(PROMPTS_TABLE).scan(**kwargs)
            items.extend(response.get('Items', []))
            last_key = response.get('LastEvaluatedKey')
            if not last_key:
                break
            kwargs['ExclusiveStartKey'] = last_key
    except ClientError as error:
        error_msg = f'Failed to list the roles: {error}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(detail = AIError.ROLE_NOT_CONFIGURED.value) from error

    return sorted(
        (PromptItem.from_item(item) for item in items),
        key = lambda prompt: (prompt.view, prompt.version)
    )


def put_prompt(prompt: PromptItem) -> None:
    '''
        Stores a role version.

        Args:
            prompt (PromptItem): Role to store.

        Raises:
            ServiceUnavailableError: If the write is rejected.
    '''
    try:
        _table(PROMPTS_TABLE).put_item(Item = prompt.to_item())
    except ClientError as error:
        error_msg = f'Failed to store the role of {prompt.view}: {error}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(detail = AIError.ROLE_NOT_CONFIGURED.value) from error


def get_cached(cache_key: str) -> Optional[ExplanationItem]:
    '''
        Returns an answer already produced for this exact key.

        A cache that cannot be read is not an error: the caller pays for a fresh
        answer instead of failing, which is the whole point of it being a cache.

        Args:
            cache_key (str): Key to look up.

        Returns:
            ExplanationItem | None: The stored answer, or None.
    '''
    try:
        response = _table(CACHE_TABLE).get_item(Key = {CACHE_PARTITION_KEY: cache_key})
    except ClientError as error:
        error_msg = f'Could not read the explanation cache: {error}'
        logger.warning(error_msg)
        return None

    item = response.get('Item')
    return ExplanationItem.from_item(item) if item else None


def put_cached(explanation: ExplanationItem) -> None:
    '''
        Stores an answer.

        A failure here is logged and swallowed for the same reason: the answer
        was already produced and the caller must get it.

        Args:
            explanation (ExplanationItem): Answer to store.
    '''
    try:
        _table(CACHE_TABLE).put_item(Item = explanation.to_item())
    except ClientError as error:
        error_msg = f'Could not store the explanation of {explanation.view}: {error}'
        logger.warning(error_msg)
