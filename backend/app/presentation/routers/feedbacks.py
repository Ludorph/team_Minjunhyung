"""피드백 API (S03 목록, S04 상세·상태, S05 단건 입력, S06 CSV 업로드)."""
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.business.services.analysis_service import AnalysisService, run_analysis_task
from app.business.services.feedback_service import CsvFormatError, FeedbackService, NotFoundError
from app.business.state.feedback_state import InvalidTransitionError
from app.persistence.models import User
from app.presentation.deps import get_current_user, get_db, require_admin
from app.presentation.schemas import (
    BatchStatus, FeedbackCreate, FeedbackDetailOut, FeedbackOut, GoldLabelIn, StatusChange,
    UploadResult,
)

router = APIRouter(prefix="/api/feedbacks", tags=["feedbacks"])


def _get_or_404(svc: FeedbackService, feedback_id: int):
    try:
        return svc.get(feedback_id)
    except NotFoundError as e:
        raise HTTPException(404, str(e)) from None


@router.get("", response_model=list[FeedbackOut])
def list_feedbacks(
    status: str | None = Query(None, description="PENDING/IN_PROGRESS/DONE"),
    sentiment: str | None = Query(None, description="POSITIVE/NEUTRAL/NEGATIVE"),
    topic: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    urgent: bool | None = None,
    db: Session = Depends(get_db), _: User = Depends(get_current_user),
):
    items = FeedbackService(db).search(status=status, sentiment=sentiment, topic=topic,
                                       date_from=date_from, date_to=date_to, urgent=urgent)
    return [FeedbackOut.of(fb) for fb in items]


@router.post("", response_model=FeedbackOut, status_code=201)
def create_feedback(body: FeedbackCreate, background: BackgroundTasks,
                    db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    try:
        fb = FeedbackService(db).create(body.content, body.source, body.written_at,
                                        body.customer_name, body.grade)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    background.add_task(run_analysis_task, [fb.id])
    return FeedbackOut.of(fb)


@router.post("/upload", response_model=UploadResult, status_code=202)
def upload_csv(background: BackgroundTasks, file: UploadFile = File(...),
               db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """CSV 일괄 업로드: 검증·저장 후 즉시 202 응답, 분석은 BackgroundTasks 로 수행."""
    try:
        out = FeedbackService(db).upload(file.filename or "", file.file.read(), user)
    except CsvFormatError as e:
        raise HTTPException(400, str(e)) from None
    background.add_task(run_analysis_task, out.feedback_ids)
    b = out.batch
    return UploadResult(
        batch_id=b.id, file_name=b.file_name, total_rows=b.total_rows, error_rows=b.error_rows,
        saved_rows=len(out.feedback_ids), errors=out.errors,
        message=f"{len(out.feedback_ids)}건 저장, {b.error_rows}건 오류. 분석이 백그라운드에서 진행됩니다.",
    )


@router.get("/batches/{batch_id}", response_model=BatchStatus)
def batch_status(batch_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    try:
        b, analyzed = FeedbackService(db).batch_status(batch_id)
    except NotFoundError as e:
        raise HTTPException(404, str(e)) from None
    return BatchStatus(batch_id=b.id, file_name=b.file_name, total_rows=b.total_rows,
                       error_rows=b.error_rows, analyzed_rows=analyzed, uploaded_at=b.uploaded_at)


@router.get("/{feedback_id}", response_model=FeedbackDetailOut)
def get_feedback(feedback_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return FeedbackDetailOut.of(_get_or_404(FeedbackService(db), feedback_id))


@router.patch("/{feedback_id}/status", response_model=FeedbackDetailOut)
def change_status(feedback_id: int, body: StatusChange, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    svc = FeedbackService(db)
    _get_or_404(svc, feedback_id)
    try:
        fb = svc.change_status(feedback_id, body.action, user)
    except InvalidTransitionError as e:
        raise HTTPException(409, str(e)) from None
    return FeedbackDetailOut.of(fb)


@router.post("/{feedback_id}/analyze", response_model=FeedbackDetailOut)
def reanalyze(feedback_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    svc = FeedbackService(db)
    _get_or_404(svc, feedback_id)
    AnalysisService(db).analyze(feedback_id)
    return FeedbackDetailOut.of(svc.get(feedback_id))


@router.put("/{feedback_id}/gold-label", status_code=204)
def set_gold_label(feedback_id: int, body: GoldLabelIn, db: Session = Depends(get_db),
                   admin: User = Depends(require_admin)):
    try:
        FeedbackService(db).set_gold_label(feedback_id, body.label, body.topic, admin)
    except NotFoundError as e:
        raise HTTPException(404, str(e)) from None
