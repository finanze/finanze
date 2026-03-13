from enum import Enum


class PublicKeychainQueries(str, Enum):
    UPSERT = """
        INSERT INTO public_keychain (key, value, algo, version, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, algo = excluded.algo, version = excluded.version, updated_at = excluded.updated_at
    """

    GET_ALL = "SELECT key, value, algo, version, updated_at FROM public_keychain"
