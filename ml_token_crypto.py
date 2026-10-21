"""Authenticated encryption of Mercado Livre credentials using a server-only key."""
from contextlib import closing
import os

from cryptography.fernet import Fernet, InvalidToken

PREFIX = 'mlenc:v1:'
KEY_ENV = 'ML_TOKEN_ENCRYPTION_KEY'
ENABLE_ENV = 'ML_TOKEN_ENCRYPTION_ENABLED'


class TokenEncryptionError(RuntimeError):
    pass


def enabled():
    return os.getenv(ENABLE_ENV) == '1'


def cipher():
    try:
        return Fernet(os.environ[KEY_ENV].encode('ascii'))
    except (KeyError, ValueError, UnicodeError) as error:
        raise TokenEncryptionError('Chave de criptografia dos tokens indisponível ou inválida.') from None


def validate_token_config():
    if enabled():
        cipher()


def reveal_token(value):
    if value is None or not value.startswith(PREFIX):
        return value
    try:
        return cipher().decrypt(value[len(PREFIX):].encode('ascii')).decode('utf-8')
    except (InvalidToken, UnicodeError, ValueError):
        raise TokenEncryptionError('Não foi possível validar a credencial criptografada.') from None


def seal_token(value):
    if value is None or value == '':
        return None
    if value.startswith(PREFIX):
        reveal_token(value)  # Never silently accept corrupted ciphertext.
        return value
    if not enabled():
        return value  # Compatibility phase only; enabled explicitly after rollout.
    return PREFIX + cipher().encrypt(value.encode('utf-8')).decode('ascii')


def migrate_tokens(bank, limit=50):
    """Bounded row locks serialize migration against concurrent token refreshes."""
    if not enabled():
        return 0
    validate_token_config()
    if not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError('invalid migration limit')
    with closing(bank()) as conn:
        with conn:
            with conn.cursor() as cur:
                cur.execute('''SELECT id,access_token,refresh_token FROM conexoes
                    WHERE (access_token IS NOT NULL AND access_token NOT LIKE %s)
                       OR (refresh_token IS NOT NULL AND refresh_token NOT LIKE %s)
                    ORDER BY id LIMIT %s FOR UPDATE SKIP LOCKED''', (PREFIX+'%',PREFIX+'%',limit))
                rows=cur.fetchall()
                for cid,access,refresh in rows:
                    cur.execute('UPDATE conexoes SET access_token=%s,refresh_token=%s WHERE id=%s',
                                (seal_token(access),seal_token(refresh),cid))
    return len(rows)
