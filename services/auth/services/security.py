'''
    Security service
'''
from passlib.context import CryptContext

# Usar bcrypt como el algoritmo de hashing preferido
pwd_context = CryptContext(schemes = ['bcrypt'], deprecated = 'auto')

def hash_password(
    password: str
) -> str:
    ''' 
        Hashing password
    '''
    return pwd_context.hash(password)

def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:
    '''
        Verifying password
    '''
    return pwd_context.verify(plain_password, hashed_password)
