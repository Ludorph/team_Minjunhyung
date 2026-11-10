"""요청/응답 DTO (pydantic)."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.business.services.feedback_service import FeedbackService
from app.business.state.feedback_state import STATUS_LABELS
from app.persistence.models import Feedback


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- 인증 ----------
class LoginRequest(BaseModel):
    login_id: str
    password: str


class UserOut(ORM):
    id: int
    login_id: str
    name: str
    role: str


class LoginResponse(BaseModel):
    token: str
    user: UserOut


# ---------- 피드백 ----------
class FeedbackCreate(BaseModel):
    content: str = Field(min_length=1)
    source: Literal["REVIEW", "CONSULT", "EMAIL"]
    written_at: datetime | None = None
    customer_name: str | None = None
    grade: Literal["VIP", "REGULAR", "NEW"] | None = None


class SentimentOut(ORM):
    label: str
    intensity: float
    confidence: float
    analyzer: str
    analyzed_at: datetime | None = None


class PriorityOut(ORM):
    score: float
    neg_intensity: float
    grade_weight: float
    time_weight: float
    is_urgent: bool
    calculated_at: datetime | None = None


class DraftOut(ORM):
    id: int
    feedback_id: int
    strategy: str
    draft_content: str
    final_content: str | None
    is_ai_generated: bool
    is_edited: bool
    confirmed: bool
    confirmed_by: int | None
    created_at: datetime
    confirmed_at: datetime | None


class HistoryOut(ORM):
    from_status: str
    to_status: str
    changed_by: int
    changed_at: datetime


class FeedbackOut(BaseModel):
    id: int
    content: str
    source: str
    written_at: datetime
    status: str
    status_label: str
    customer_name: str | None
    grade: str | None
    batch_id: int | None
    sentiment: SentimentOut | None
    topics: list[str]
    priority: PriorityOut | None
    tags: list[str]

    @classmethod
    def of(cls, fb: Feedback) -> "FeedbackOut":
        return cls(
            id=fb.id, content=fb.content, source=fb.source, written_at=fb.written_at,
            status=fb.status, status_label=STATUS_LABELS[fb.status],
            customer_name=fb.customer.name if fb.customer else None, grade=fb.grade,
            batch_id=fb.batch_id,
            sentiment=SentimentOut.model_validate(fb.sentiment) if fb.sentiment else None,
            topics=fb.topic_names,
            priority=PriorityOut.model_validate(fb.priority) if fb.priority else None,
            tags=FeedbackService.tags_for(fb),
        )


class FeedbackDetailOut(FeedbackOut):
    drafts: list[DraftOut]
    histories: list[HistoryOut]

    @classmethod
    def of(cls, fb: Feedback) -> "FeedbackDetailOut":
        base = FeedbackOut.of(fb).model_dump()
        return cls(**base,
                   drafts=[DraftOut.model_validate(d) for d in fb.drafts],
                   histories=[HistoryOut.model_validate(h) for h in fb.histories])


class StatusChange(BaseModel):
    action: Literal["start", "complete", "reopen"]


class UploadError(BaseModel):
    row: int
    reason: str


class UploadResult(BaseModel):
    batch_id: int
    file_name: str
    total_rows: int
    error_rows: int
    saved_rows: int
    errors: list[UploadError]
    message: str


class BatchStatus(BaseModel):
    batch_id: int
    file_name: str
    total_rows: int
    error_rows: int
    analyzed_rows: int
    uploaded_at: datetime


class GoldLabelIn(BaseModel):
    label: Literal["POSITIVE", "NEUTRAL", "NEGATIVE"]
    topic: Literal["품질", "배송", "가격", "서비스", "기타"]


# ---------- 답변 초안 ----------
class DraftCreate(BaseModel):
    strategy: Literal["APOLOGY", "GUIDANCE", "THANKS"] | None = None


class DraftEdit(BaseModel):
    text: str = Field(min_length=1)


class DraftConfirm(BaseModel):
    final_content: str | None = None


# ---------- 대시보드 ----------
class DashboardSummary(BaseModel):
    total: int
    by_status: dict[str, int]
    by_sentiment: dict[str, int]
    by_topic: dict[str, int]
    urgent_count: int
    daily_trend: list[dict]


class AccuracyReport(BaseModel):
    sample_size: int
    sentiment_accuracy: float | None
    topic_accuracy: float | None
    items: list[dict]
