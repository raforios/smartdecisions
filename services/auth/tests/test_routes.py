'''
    Route-level tests: only an ADMIN signs a user up (Rafael, 19-oct-2026).
'''
import asyncio
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from controllers.users import get_current_admin_user
from main import app
from routes.auth import router
from schemas.role import Role
from schemas.users import UserResponse
from services.exceptions import ForbiddenError


def _user(role: Role) -> UserResponse:
    '''
        An active user of `role`, as the token dependency returns it.

        Args:
            role (Role): The user's role.

        Returns:
            UserResponse: The user.
    '''
    now = datetime.now(timezone.utc)
    return UserResponse(email = 'someone@bearsoft.com.bo', first_name = 'Some',
                        last_name = 'One', client = 'acme', role = role, status = True,
                        date_register = now, date_update = now)


def test_signup_requires_a_token() -> None:
    '''Without a token the sign-up is refused before touching the table.'''
    response = TestClient(app).post('/v1/auth/signup', json = {
        'email': 'new@bearsoft.com.bo', 'first_name': 'New', 'last_name': 'User',
        'password': 'a-long-password'})
    assert response.status_code in (401, 403)


def test_signup_is_guarded_by_the_admin_dependency() -> None:
    '''The sign-up route carries the same guard as the user management.'''
    route = next(r for r in router.routes if r.path == '/v1/auth/signup')
    guards = [dependency.call for dependency in route.dependant.dependencies]
    assert get_current_admin_user in guards


def test_admin_guard_accepts_only_admin() -> None:
    '''An ADMIN passes; a MANAGER is forbidden.'''
    admin = _user(Role.ADMIN)
    assert asyncio.run(get_current_admin_user(admin)) is admin
    with pytest.raises(ForbiddenError):
        asyncio.run(get_current_admin_user(_user(Role.MANAGER)))
