from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.business.services.auth_service import AuthError, AuthService
from app.persistence.models import User
from app.presentation.deps import bearer_token, get_current_user, get_db
from app.presentation.schemas import LoginRequest, LoginResponse, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth (S01)"])


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    try:
        token, user = AuthService(db).login(body.login_id, body.password)
    except AuthError as e:
        raise HTTPException(401, str(e)) from None
    return LoginResponse(token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/logout", status_code=204)
def logout(token: str = Depends(bearer_token)):
    AuthService.logout(token)
