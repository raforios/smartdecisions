'''
    Security service

    Passwords are hashed with `bcrypt` directly. passlib 1.7.4 is no longer
    maintained and breaks with bcrypt 4.1 and later, which forced both to be
    pinned (Rafael, 19-oct-2026: no pinned versions). The hashes are the same
    `$2b$` format, so the passwords already stored keep working.
'''
import bcrypt

# bcrypt reads only the first 72 bytes of a password. passlib cut longer ones
# silently; bcrypt 5 rejects them instead, so they are cut here the same way
# and a password stored before keeps matching.
BCRYPT_MAX_BYTES = 72


def _password_bytes(password: str) -> bytes:
    '''
        The bytes bcrypt hashes: the UTF-8 password, cut at 72 bytes.

        Args:
            password (str): The plain password.

        Returns:
            bytes: What bcrypt receives.
    '''
    return password.encode('utf-8')[:BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    '''
        Hashes a password with a fresh salt.

        Args:
            password (str): The plain password.

        Returns:
            str: The bcrypt hash, as stored in `hashed_password`.
    '''
    return bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt()).decode('utf-8')


def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:
    '''
        Checks a password against its stored hash.

        Args:
            plain_password (str): The password typed by the user.
            hashed_password (str): The stored bcrypt hash.

        Returns:
            bool: True when they match; False also for a malformed hash.
    '''
    try:
        return bcrypt.checkpw(_password_bytes(plain_password), hashed_password.encode('utf-8'))
    except ValueError:
        return False
