'''
    DynamoDB items for the AI interpretation service.

    Two tables, two different jobs, and keeping them apart is deliberate:

      ai_prompts       PK: view (S)   SK: version (N)
          The expert role each view is explained by. Versioned so a wording
          change is a new row and not an edit that loses what came before, and
          so the version can take part in the cache key: retuning the role
          invalidates what was cached without deleting anything.

      ai_explanations  PK: cache_key (S)
          Answers already produced, with a TTL attribute. It can be emptied
          whole without losing anything — that is what makes it a cache and not
          storage.
'''
from dataclasses import dataclass
from typing import Any, Dict, List


PROMPTS_PARTITION_KEY = 'view'
PROMPTS_SORT_KEY = 'version'
CACHE_PARTITION_KEY = 'cache_key'
CACHE_TTL_ATTRIBUTE = 'expires_at'


# Nine fields because a stored role is nine facts: which view, which version,
# who, how to read it, what never to do, the ceiling, the model, whether it is
# in force and when it was written. Grouping any of them would only hide one.
@dataclass(frozen = True)
class PromptItem: # pylint: disable=too-many-instance-attributes
    '''
        One versioned role, as stored.

        `rules` is a list rather than a paragraph so adding a prohibition is a
        row edit and not a rewrite of the whole prompt.
    '''
    view: str
    version: int
    role: str
    instructions: str
    rules: List[str]
    max_tokens: int
    model_id: str
    active: bool
    created_at: str

    @classmethod
    def from_item(cls, item: Dict[str, Any]) -> 'PromptItem':
        '''
            Builds the record from a raw DynamoDB item.

            Args:
                item (Dict[str, Any]): Item as returned by boto3.

            Returns:
                PromptItem: The typed record.
        '''
        return cls(
            view = str(item[PROMPTS_PARTITION_KEY]),
            version = int(item[PROMPTS_SORT_KEY]),
            role = str(item.get('role', '')),
            instructions = str(item.get('instructions', '')),
            rules = [str(rule) for rule in item.get('rules', [])],
            max_tokens = int(item.get('max_tokens', 0)),
            model_id = str(item.get('model_id', '')),
            active = bool(item.get('active', True)),
            created_at = str(item.get('created_at', ''))
        )

    def to_item(self) -> Dict[str, Any]:
        '''
            Renders the record as the item DynamoDB stores.

            Returns:
                Dict[str, Any]: Item ready for put_item.
        '''
        return {
            PROMPTS_PARTITION_KEY: self.view,
            PROMPTS_SORT_KEY: self.version,
            'role': self.role,
            'instructions': self.instructions,
            'rules': self.rules,
            'max_tokens': self.max_tokens,
            'model_id': self.model_id,
            'active': self.active,
            'created_at': self.created_at,
        }


# Eight fields because a cached answer has to carry what produced it: serving
# text without its role, model and version would make a stale answer
# indistinguishable from a fresh one.
@dataclass(frozen = True)
class ExplanationItem: # pylint: disable=too-many-instance-attributes
    '''
        One cached answer.

        The key is a fingerprint of view, payload and prompt version together:
        if any of the three differs, the answer would differ too, so it must not
        be served from here.
    '''
    cache_key: str
    view: str
    text: str
    role: str
    model_id: str
    prompt_version: int
    generated_at: str
    expires_at: int

    @classmethod
    def from_item(cls, item: Dict[str, Any]) -> 'ExplanationItem':
        '''
            Builds the record from a raw DynamoDB item.

            Args:
                item (Dict[str, Any]): Item as returned by boto3.

            Returns:
                ExplanationItem: The typed record.
        '''
        return cls(
            cache_key = str(item[CACHE_PARTITION_KEY]),
            view = str(item.get('view', '')),
            text = str(item.get('text', '')),
            role = str(item.get('role', '')),
            model_id = str(item.get('model_id', '')),
            prompt_version = int(item.get('prompt_version', 0)),
            generated_at = str(item.get('generated_at', '')),
            expires_at = int(item.get(CACHE_TTL_ATTRIBUTE, 0))
        )

    def to_item(self) -> Dict[str, Any]:
        '''
            Renders the record as the item DynamoDB stores.

            Returns:
                Dict[str, Any]: Item ready for put_item.
        '''
        return {
            CACHE_PARTITION_KEY: self.cache_key,
            'view': self.view,
            'text': self.text,
            'role': self.role,
            'model_id': self.model_id,
            'prompt_version': self.prompt_version,
            'generated_at': self.generated_at,
            CACHE_TTL_ATTRIBUTE: self.expires_at,
        }
