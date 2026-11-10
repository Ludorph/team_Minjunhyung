"""Repository (persistence 계층): 비즈니스 계층은 SQL 대신 이 클래스들을 사용한다."""
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.persistence.models import (
    Customer, Feedback, FeedbackTopic, GoldLabel, GradeWeight, PriorityScore,
    ResponseDraft, SentimentResult, StatusHistory, Topic, UploadBatch, User,
)


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def find_by_login_id(self, login_id: str) -> User | None:
        return self.db.scalar(select(User).where(User.login_id == login_id))


class CustomerRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create(self, name: str, grade: str) -> Customer:
        c = self.db.scalar(select(Customer).where(Customer.name == name, Customer.grade == grade))
        if c is None:
            c = Customer(name=name, grade=grade)
            self.db.add(c)
            self.db.flush()
        return c


class GradeWeightRepository:
    def __init__(self, db: Session):
        self.db = db

    def as_dict(self) -> dict[str, float]:
        return {g.grade: float(g.weight) for g in self.db.scalars(select(GradeWeight))}


class TopicRepository:
    def __init__(self, db: Session):
        self.db = db

    def by_name(self) -> dict[str, Topic]:
        return {t.name: t for t in self.db.scalars(select(Topic))}


class UploadBatchRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, batch: UploadBatch) -> UploadBatch:
        self.db.add(batch)
        self.db.flush()
        return batch

    def get(self, batch_id: int) -> UploadBatch | None:
        return self.db.get(UploadBatch, batch_id)

    def analyzed_count(self, batch_id: int) -> int:
        return self.db.scalar(
            select(func.count()).select_from(Feedback)
            .join(SentimentResult, SentimentResult.feedback_id == Feedback.id)
            .where(Feedback.batch_id == batch_id)
        ) or 0


class FeedbackRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, fb: Feedback) -> Feedback:
        self.db.add(fb)
        self.db.flush()
        return fb

    def get(self, feedback_id: int) -> Feedback | None:
        return self.db.get(Feedback, feedback_id)

    def search(self, status: str | None = None, sentiment: str | None = None, topic: str | None = None,
               date_from: datetime | None = None, date_to: datetime | None = None,
               urgent: bool | None = None) -> list[Feedback]:
        """우선순위 점수 내림차순 정렬된 목록 (S03)."""
        q = (select(Feedback)
             .outerjoin(PriorityScore, PriorityScore.feedback_id == Feedback.id)
             .outerjoin(SentimentResult, SentimentResult.feedback_id == Feedback.id)
             .options(selectinload(Feedback.customer), selectinload(Feedback.sentiment),
                      selectinload(Feedback.priority),
                      selectinload(Feedback.topic_links).selectinload(FeedbackTopic.topic)))
        if status:
            q = q.where(Feedback.status == status)
        if sentiment:
            q = q.where(SentimentResult.label == sentiment)
        if topic:
            q = q.where(Feedback.topic_links.any(FeedbackTopic.topic.has(Topic.name == topic)))
        if date_from:
            q = q.where(Feedback.written_at >= date_from)
        if date_to:
            q = q.where(Feedback.written_at <= date_to)
        if urgent is not None:
            q = q.where(PriorityScore.is_urgent.is_(urgent))
        q = q.order_by(func.coalesce(PriorityScore.score, -1).desc(), Feedback.written_at.desc())
        return list(self.db.scalars(q))

    # ---- 대시보드 집계 ----
    def count_by_status(self) -> dict[str, int]:
        rows = self.db.execute(select(Feedback.status, func.count()).group_by(Feedback.status))
        return {s: n for s, n in rows}

    def count_by_sentiment(self) -> dict[str, int]:
        rows = self.db.execute(select(SentimentResult.label, func.count()).group_by(SentimentResult.label))
        return {s: n for s, n in rows}

    def count_by_topic(self) -> dict[str, int]:
        rows = self.db.execute(
            select(Topic.name, func.count()).join(FeedbackTopic, FeedbackTopic.topic_id == Topic.id)
            .group_by(Topic.name))
        return {s: n for s, n in rows}

    def count_urgent_open(self) -> int:
        return self.db.scalar(
            select(func.count()).select_from(PriorityScore)
            .join(Feedback, Feedback.id == PriorityScore.feedback_id)
            .where(PriorityScore.is_urgent.is_(True), Feedback.status != "DONE")) or 0

    def daily_sentiment(self) -> list[tuple[str, str, int]]:
        day = func.date(Feedback.written_at)
        rows = self.db.execute(
            select(day, SentimentResult.label, func.count())
            .join(SentimentResult, SentimentResult.feedback_id == Feedback.id)
            .group_by(day, SentimentResult.label).order_by(day))
        return [(d, label, n) for d, label, n in rows]


class ResponseDraftRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, d: ResponseDraft) -> ResponseDraft:
        self.db.add(d)
        self.db.flush()
        return d

    def get(self, draft_id: int) -> ResponseDraft | None:
        return self.db.get(ResponseDraft, draft_id)


class StatusHistoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, h: StatusHistory) -> StatusHistory:
        self.db.add(h)
        return h


class GoldLabelRepository:
    def __init__(self, db: Session):
        self.db = db

    def upsert(self, feedback_id: int, label: str, topic: str, user_id: int) -> GoldLabel:
        g = self.db.get(GoldLabel, feedback_id)
        if g is None:
            g = GoldLabel(feedback_id=feedback_id, label=label, topic=topic, labeled_by=user_id)
            self.db.add(g)
        else:
            g.label, g.topic, g.labeled_by = label, topic, user_id
        return g

    def all_with_feedback(self) -> list[GoldLabel]:
        return list(self.db.scalars(select(GoldLabel).options(selectinload(GoldLabel.feedback))))
