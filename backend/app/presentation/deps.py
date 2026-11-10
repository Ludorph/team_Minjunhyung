"""공통 의존성: DB 세션, 현재 사용자(토큰 스텁)."""
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.business.services.auth_service import AuthError, AuthService
from app.persistence.database import get_db
from app.persistence.models import Role, User

__all__ = ["get_db", "get_current_user", "require_admin", "bearer_token"]


def bearer_token(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "로그인이 필요합니다.")
    return authorization.split(" ", 1)[1].strip()


def get_current_user(token: str = Depends(bearer_token), db: Session = Depends(get_db)) -> User:
    try:
        return AuthService(db).resolve(token)
    except AuthError as e:
        raise HTTPException(401, str(e)) from None


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.ADMIN:
        raise HTTPException(403, "관리자 전용 기능입니다.")
    return user
