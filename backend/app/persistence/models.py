"""ORM 모델 (persistence 계층). 테이블/컬럼은 09_erd.puml 과 1:1 대응한다.

클래스명은 도메인 모델(03_class_domain.puml)의 이름을 따른다.
도메인 열거형(Role, CustomerGrade, SentimentLabel)은 문자열 상수로 표현한다.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.persistence.database import Base


def Dec(p: int, s: int) -> Numeric:  # noqa: N802 - DECIMAL(p,s) 를 float 로 다룬다
    return Numeric(p, s, asdecimal=False)


# 도메인 열거형
class Role:
    AGENT = "AGENT"
    ADMIN = "ADMIN"


class CustomerGrade:
    VIP = "VIP"
    REGULAR = "REGULAR"
    NEW = "NEW"
    ALL = (VIP, REGULAR, NEW)


class SentimentLabel:
    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    NEGATIVE = "NEGATIVE"
    ALL = (POSITIVE, NEUTRAL, NEGATIVE)


SOURCES = ("REVIEW", "CONSULT", "EMAIL")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    login_id: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(50))
    role: Mapped[str] = mapped_column(String(10))  # AGENT/ADMIN
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class GradeWeight(Base):
    __tablename__ = "grade_weights"
    grade: Mapped[str] = mapped_column(String(10), primary_key=True)
    weight: Mapped[float] = mapped_column(Dec(3, 2))


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    grade: Mapped[str] = mapped_column(String(10), ForeignKey("grade_weights.grade"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    feedbacks: Mapped[list["Feedback"]] = relationship(back_populates="customer")


class UploadBatch(Base):
    __tablename__ = "upload_batches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_name: Mapped[str] = mapped_column(String(255))
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    error_rows: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    feedbacks: Mapped[list["Feedback"]] = relationship(back_populates="batch")


class Feedback(Base):
    __tablename__ = "feedbacks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("upload_batches.id"), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(10))  # REVIEW/CONSULT/EMAIL
    written_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(12), default="PENDING")  # PENDING/IN_PROGRESS/DONE
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    customer: Mapped["Customer | None"] = relationship(back_populates="feedbacks")
    batch: Mapped["UploadBatch | None"] = relationship(back_populates="feedbacks")
    sentiment: Mapped["SentimentResult | None"] = relationship(
        back_populates="feedback", uselist=False, cascade="all, delete-orphan")
    priority: Mapped["PriorityScore | None"] = relationship(
        back_populates="feedback", uselist=False, cascade="all, delete-orphan")
    topic_links: Mapped[list["FeedbackTopic"]] = relationship(
        back_populates="feedback", cascade="all, delete-orphan")
    drafts: Mapped[list["ResponseDraft"]] = relationship(
        back_populates="feedback", cascade="all, delete-orphan", order_by="ResponseDraft.id")
    histories: Mapped[list["StatusHistory"]] = relationship(
        back_populates="feedback", cascade="all, delete-orphan", order_by="StatusHistory.id")
    gold_label: Mapped["GoldLabel | None"] = relationship(
        back_populates="feedback", uselist=False, cascade="all, delete-orphan")

    def elapsed_hours(self, now: datetime | None = None) -> float:
        now = now or datetime.now()
        return max(0.0, (now - self.written_at).total_seconds() / 3600)

    @property
    def topic_names(self) -> list[str]:
        return [link.topic.name for link in self.topic_links]

    @property
    def grade(self) -> str | None:
        return self.customer.grade if self.customer else None


class SentimentResult(Base):
    __tablename__ = "sentiment_results"
    feedback_id: Mapped[int] = mapped_column(ForeignKey("feedbacks.id"), primary_key=True)
    label: Mapped[str] = mapped_column(String(10))
    intensity: Mapped[float] = mapped_column(Dec(3, 2))
    confidence: Mapped[float] = mapped_column(Dec(3, 2))
    analyzer: Mapped[str] = mapped_column(String(10))  # LLM/RULE
    analyzed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    feedback: Mapped["Feedback"] = relationship(back_populates="sentiment")


class Topic(Base):
    __tablename__ = "topics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(20), unique=True)


class FeedbackTopic(Base):
    __tablename__ = "feedback_topics"
    feedback_id: Mapped[int] = mapped_column(ForeignKey("feedbacks.id"), primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), primary_key=True)
    score: Mapped[float | None] = mapped_column(Dec(3, 2), nullable=True)

    feedback: Mapped["Feedback"] = relationship(back_populates="topic_links")
    topic: Mapped["Topic"] = relationship()


class PriorityScore(Base):
    __tablename__ = "priority_scores"
    feedback_id: Mapped[int] = mapped_column(ForeignKey("feedbacks.id"), primary_key=True)
    score: Mapped[float] = mapped_column(Dec(5, 2))
    neg_intensity: Mapped[float] = mapped_column(Dec(3, 2))
    grade_weight: Mapped[float] = mapped_column(Dec(3, 2))
    time_weight: Mapped[float] = mapped_column(Dec(3, 2))
    is_urgent: Mapped[bool] = mapped_column(Boolean, default=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    feedback: Mapped["Feedback"] = relationship(back_populates="priority")


class ResponseDraft(Base):
    __tablename__ = "response_drafts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feedback_id: Mapped[int] = mapped_column(ForeignKey("feedbacks.id"))
    strategy: Mapped[str] = mapped_column(String(12))
    draft_content: Mapped[str] = mapped_column(Text)
    final_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)  # False = 템플릿 대체 (UC-04 E1)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    feedback: Mapped["Feedback"] = relationship(back_populates="drafts")

    @property
    def is_edited(self) -> bool:
        """담당자가 초안 문구를 바꿨는지."""
        return bool(self.final_content) and self.final_content != self.draft_content

    def edit(self, text: str) -> None:
        self.final_content = text

    def confirm(self, user: User) -> None:
        if not self.final_content:
            self.final_content = self.draft_content
        self.confirmed = True
        self.confirmed_by = user.id
        self.confirmed_at = datetime.now()


class StatusHistory(Base):
    __tablename__ = "status_histories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feedback_id: Mapped[int] = mapped_column(ForeignKey("feedbacks.id"))
    from_status: Mapped[str] = mapped_column(String(12))
    to_status: Mapped[str] = mapped_column(String(12))
    changed_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    feedback: Mapped["Feedback"] = relationship(back_populates="histories")


class GoldLabel(Base):
    __tablename__ = "gold_labels"
    feedback_id: Mapped[int] = mapped_column(ForeignKey("feedbacks.id"), primary_key=True)
    label: Mapped[str] = mapped_column(String(10))
    topic: Mapped[str] = mapped_column(String(20))
    labeled_by: Mapped[int] = mapped_column(ForeignKey("users.id"))

    feedback: Mapped["Feedback"] = relationship(back_populates="gold_label")
