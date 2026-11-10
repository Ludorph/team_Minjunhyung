"""대시보드(S02) / 분석 정확도(S07, 관리자 전용) API."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.business.services.dashboard_service import DashboardService
from app.persistence.models import User
from app.presentation.deps import get_current_user, get_db, require_admin
from app.presentation.schemas import AccuracyReport, DashboardSummary

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def summary(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return DashboardService(db).summary()


@router.get("/accuracy", response_model=AccuracyReport)
def accuracy(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return DashboardService(db).accuracy()
