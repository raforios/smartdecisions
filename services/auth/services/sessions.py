'''
    Pure rules about sign-ins and about who belongs to an account. No database
    and no environment: the CI runs the AUTH suite without a `.env`, so these
    are the parts of the feature that suite can check.
'''
from datetime import datetime
from typing import Any


def login_update(
    user_item: dict[str, Any],
    now: datetime
) -> tuple[str, dict[str, Any]]:
    '''
        The DynamoDB update that records one sign-in: this one becomes the last,
        the one before it becomes the previous, and the count grows by one.

        Args:
            user_item (dict[str, Any]): The user as stored, before this sign-in.
            now (datetime): When this sign-in happened.

        Returns:
            tuple[str, dict[str, Any]]: Update expression and its values.
    '''
    expression = ('SET last_login = :now, '
                  'login_count = if_not_exists(login_count, :zero) + :one')
    values: dict[str, Any] = {':now': now.isoformat(), ':zero': 0, ':one': 1}
    if user_item.get('last_login'):
        expression += ', previous_login = :previous'
        values[':previous'] = user_item['last_login']
    return expression, values


def company_members(
    items: list[dict[str, Any]],
    viewer_email: str,
    viewer_client: str | None,
    is_admin: bool
) -> list[dict[str, Any]]:
    '''
        The users one person may see: an administrator sees everyone; anybody
        else, the users of their own `client`. Somebody without a client is an
        account of one and sees only themselves: matching "no client" would
        show every unrelated user who also has none.

        Args:
            items (list[dict[str, Any]]): Every stored user.
            viewer_email (str): Who asks.
            viewer_client (str | None): The client of who asks.
            is_admin (bool): Whether who asks is an administrator.

        Returns:
            list[dict[str, Any]]: The visible users, by e-mail.
    '''
    if is_admin:
        visible = items
    elif viewer_client:
        visible = [item for item in items if item.get('client') == viewer_client]
    else:
        visible = [item for item in items if item.get('email') == viewer_email]
    return sorted(visible, key = lambda item: str(item.get('email')))
