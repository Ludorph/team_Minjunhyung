"""간단한 비밀번호 해시 (hashlib). 과제용이며 운영 환경에서는 bcrypt/argon2 를 사용해야 한다."""
import hashlib
import hmac

_SALT = "feedbackcare-pbl"


def hash_password(password: str) -> str:
    return hashlib.sha256((_SALT + password).encode("utf-8")).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    return hmac.compare_digest(hash_password(password), password_hash)
