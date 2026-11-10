"""인증 (과제용 스텁): 로그인 시 무작위 토큰을 발급해 메모리에 보관한다.
서버 재시작 시 토큰이 사라지며, 운영 환경에서는 JWT 등으로 교체해야 한다."""
import secrets

from sqlalchemy.orm import Session

from app.infra.security import verify_password
from app.persistence.models import User
from app.persistence.repositories import UserRepository

_TOKENS: dict[str, int] = {}  # token -> user_id


class AuthError(Exception):
    pass


class AuthService:
    def __init__(self, db: Session):
        self.users = UserRepository(db)

    def login(self, login_id: str, password: str) -> tuple[str, User]:
        user = self.users.find_by_login_id(login_id)
        if user is None or not verify_password(password, user.password_hash):
            raise AuthError("아이디 또는 비밀번호가 올바르지 않습니다.")
        token = secrets.token_hex(16)
        _TOKENS[token] = user.id
        return token, user

    def resolve(self, token: str) -> User:
        uid = _TOKENS.get(token)
        user = self.users.get(uid) if uid else None
        if user is None:
            raise AuthError("로그인이 필요합니다.")
        return user

    @staticmethod
    def logout(token: str) -> None:
        _TOKENS.pop(token, None)
