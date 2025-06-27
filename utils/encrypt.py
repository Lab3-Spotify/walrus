from cryptography.fernet import Fernet
from django.conf import settings


def get_fernet():
    key = settings.MEMBER_API_TOKEN_SECRET_KEY
    return Fernet(key)


def encrypt_value(value: str) -> str:
    f = get_fernet()
    return f.encrypt(value.encode()).decode()


def decrypt_value(token: str) -> str:
    f = get_fernet()
    return f.decrypt(token.encode()).decode()
