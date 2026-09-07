'''
    The only piece that talks to Bedrock.

    Isolated on purpose: everything else in this service reasons about views,
    roles and cache, and none of it should know how a model is invoked. The day
    the provider changes, this file changes.

    Two facts about Bedrock that cost time to find and are worth stating here:

      - **Inference profiles are mandatory.** The bare model id answers
        `ValidationException: on-demand throughput isn't supported`. The id must
        carry the `us.` prefix.
      - **Anthropic models need a use-case form** submitted once per account
        before the first call, and it takes up to fifteen minutes to propagate.
        Until then every call fails with ResourceNotFoundException.
'''
import json
from typing import Any, Dict, List

import boto3
from botocore.exceptions import ClientError

from schemas.ai import AIError
from services.environment import load_and_validate_env_vars
from services.exceptions import ServiceUnavailableError
from services.logger_config import custom_logger as logger


ENV_VARS = load_and_validate_env_vars({
    'BEDROCK_REGION': str,
    'BEDROCK_ANTHROPIC_VERSION': str,
    'BEDROCK_TEMPERATURE': float,
})

BEDROCK_REGION = ENV_VARS['BEDROCK_REGION']

# The payload version Bedrock expects for Anthropic models. It is not the model
# version and it is not ours to guess, so it is configured.
ANTHROPIC_VERSION = ENV_VARS['BEDROCK_ANTHROPIC_VERSION']

# Low by default: this service explains figures that are already computed, and
# the same screen explained twice should not read differently.
TEMPERATURE = ENV_VARS['BEDROCK_TEMPERATURE']

_client = boto3.client('bedrock-runtime', region_name = BEDROCK_REGION)


def invoke(
    model_id: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int
) -> Dict[str, Any]:
    '''
        Asks the model for one answer and returns it with what it cost.

        Args:
            model_id (str): Bedrock inference profile, `us.` prefix included.
            system_prompt (str): The role and its rules.
            user_prompt (str): The view payload and the question.
            max_tokens (int): Ceiling on the answer.

        Returns:
            Dict[str, Any]: `text`, `input_tokens` and `output_tokens`.

        Raises:
            ServiceUnavailableError: If Bedrock cannot be reached or refuses.
    '''
    body = json.dumps({
        'anthropic_version': ANTHROPIC_VERSION,
        'max_tokens': max_tokens,
        'temperature': TEMPERATURE,
        'system': system_prompt,
        'messages': [{'role': 'user', 'content': user_prompt}],
    })

    try:
        response = _client.invoke_model(modelId = model_id, body = body)
        payload = json.loads(response['body'].read())
    except ClientError as error:
        error_msg = f'Bedrock refused the call to {model_id}: {error}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(detail = AIError.MODEL_UNAVAILABLE.value) from error
    except (KeyError, ValueError) as error:
        error_msg = f'Bedrock answered something unreadable from {model_id}: {error}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(detail = AIError.MODEL_UNAVAILABLE.value) from error

    return {
        'text': _first_text(payload.get('content', [])),
        'input_tokens': int(payload.get('usage', {}).get('input_tokens', 0)),
        'output_tokens': int(payload.get('usage', {}).get('output_tokens', 0)),
    }


def _first_text(content: List[Dict[str, Any]]) -> str:
    '''
        Returns the text of the answer.

        The response is a list of blocks; a refusal or a tool call would carry
        no text at all, and returning an empty string lets the caller treat that
        as a refusal rather than publish nothing as if it were an answer.

        Args:
            content (List[Dict[str, Any]]): Content blocks from the model.

        Returns:
            str: The first text block, stripped, or an empty string.
    '''
    for block in content:
        if block.get('type') == 'text':
            return str(block.get('text', '')).strip()
    return ''
