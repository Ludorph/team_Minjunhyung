"""답변 초안 API (S04)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.business.services.feedback_service import NotFoundError
from app.business.services.response_service import ResponseService
from app.persistence.models import User
from app.presentation.deps import get_current_user, get_db
from app.presentation.schemas import DraftConfirm, DraftCreate, DraftEdit, DraftOut

router = APIRouter(prefix="/api", tags=["drafts (S04)"])


@router.post("/feedbacks/{feedback_id}/drafts", response_model=DraftOut, status_code=201)
def create_draft(feedback_id: int, body: DraftCreate | None = None, db: Session = Depends(get_db),
                 _: User = Depends(get_current_user)):
    try:
        return ResponseService(db).create_draft(feedback_id, body.strategy if body else None)
    except NotFoundError as e:
        raise HTTPException(404, str(e)) from None
    except ValueError as e:
        raise HTTPException(422, str(e)) from None


@router.patch("/drafts/{draft_id}", response_model=DraftOut)
def edit_draft(draft_id: int, body: DraftEdit, db: Session = Depends(get_db),
               _: User = Depends(get_current_user)):
    try:
        return ResponseService(db).edit(draft_id, body.text)
    except NotFoundError as e:
        raise HTTPException(404, str(e)) from None


@router.patch("/drafts/{draft_id}/confirm", response_model=DraftOut)
def confirm_draft(draft_id: int, body: DraftConfirm | None = None, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    try:
        return ResponseService(db).confirm(draft_id, body.final_content if body else None, user)
    except NotFoundError as e:
        raise HTTPException(404, str(e)) from None
