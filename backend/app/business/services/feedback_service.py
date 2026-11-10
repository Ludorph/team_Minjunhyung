"""피드백 등록·조회·CSV 업로드·상태 변경 (UC-01, 상태 관리)."""
import csv
import io
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from app.business.priority.decorators import decorate
from app.business.state.feedback_state import apply_transition
from app.persistence.models import (
    SOURCES,
    CustomerGrade,
    Feedback,
    GoldLabel,
    StatusHistory,
    UploadBatch,
    User,
)
from app.persistence.repositories import (
    CustomerRepository,
    FeedbackRepository,
    GoldLabelRepository,
    StatusHistoryRepository,
    UploadBatchRepository,
)

REQUIRED_COLUMNS = ["customer_name", "grade", "source", "written_at", "content"]
DATE_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d")


class CsvFormatError(Exception):
    """파일 형식 오류 (→ 400)."""


class NotFoundError(Exception):
    pass


@dataclass
class UploadOutcome:
    batch: UploadBatch
    feedback_ids: list[int]
    errors: list[dict] = field(default_factory=list)


def parse_datetime(value: str) -> datetime:
    value = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"날짜 형식 오류: '{value}'")


class FeedbackService:
    def __init__(self, db: Session):
        self.db = db
        self.feedbacks = FeedbackRepository(db)
        self.customers = CustomerRepository(db)
        self.batches = UploadBatchRepository(db)
        self.histories = StatusHistoryRepository(db)

    # ---------- 등록 ----------
    def _build(self, content: str, source: str, written_at: datetime,
               customer_name: str | None, grade: str | None, batch: UploadBatch | None = None) -> Feedback:
        content = (content or "").strip()
        source = (source or "").strip().upper()
        if not content:
            raise ValueError("content 가 비어 있습니다")
        if source not in SOURCES:
            raise ValueError(f"source 는 {'/'.join(SOURCES)} 중 하나여야 합니다: '{source}'")
        customer = None
        name = (customer_name or "").strip()
        grade = (grade or "").strip().upper()
        if name:
            if grade not in CustomerGrade.ALL:
                raise ValueError(f"grade 는 {'/'.join(CustomerGrade.ALL)} 중 하나여야 합니다: '{grade}'")
            customer = self.customers.get_or_create(name, grade)
        elif grade and grade not in CustomerGrade.ALL:
            raise ValueError(f"알 수 없는 grade: '{grade}'")
        return Feedback(content=content, source=source, written_at=written_at,
                        customer=customer, batch=batch, status="PENDING")

    def create(self, content: str, source: str, written_at: datetime | None,
               customer_name: str | None, grade: str | None) -> Feedback:
        fb = self._build(content, source, written_at or datetime.now(), customer_name, grade)
        self.feedbacks.add(fb)
        self.db.commit()
        return fb

    def upload(self, file_name: str, raw: bytes, user: User) -> UploadOutcome:
        """CSV 형식·필수 필드 검증 후 일괄 저장 (분석은 호출 측이 백그라운드로 실행)."""
        if not file_name or not file_name.lower().endswith(".csv"):
            raise CsvFormatError("CSV 파일(.csv)만 업로드할 수 있습니다.")
        if not raw.strip():
            raise CsvFormatError("빈 파일입니다.")
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                text = raw.decode("cp949")
            except UnicodeDecodeError:
                raise CsvFormatError("파일 인코딩을 읽을 수 없습니다 (UTF-8 또는 CP949).") from None
        reader = csv.DictReader(io.StringIO(text))
        header = [h.strip() for h in (reader.fieldnames or [])]
        missing = [c for c in REQUIRED_COLUMNS if c not in header]
        if missing:
            raise CsvFormatError(f"필수 컬럼 누락: {', '.join(missing)} (필요: {', '.join(REQUIRED_COLUMNS)})")

        batch = self.batches.add(UploadBatch(file_name=file_name, total_rows=0, error_rows=0, uploaded_by=user.id))
        ids, errors, total = [], [], 0
        for row_no, row in enumerate(reader, start=2):  # 1행은 헤더
            row = {(k or "").strip(): (v or "") for k, v in row.items()}
            if not any(v.strip() for v in row.values()):
                continue  # 빈 줄 무시
            total += 1
            try:
                fb = self._build(row["content"], row["source"], parse_datetime(row["written_at"]),
                                 row["customer_name"], row["grade"], batch)
                self.feedbacks.add(fb)
                ids.append(fb.id)
            except ValueError as e:
                errors.append({"row": row_no, "reason": str(e)})
        if total == 0:
            self.db.rollback()
            raise CsvFormatError("데이터 행이 없습니다.")
        batch.total_rows, batch.error_rows = total, len(errors)
        self.db.commit()
        return UploadOutcome(batch=batch, feedback_ids=ids, errors=errors)

    # ---------- 조회 ----------
    def get(self, feedback_id: int) -> Feedback:
        fb = self.feedbacks.get(feedback_id)
        if fb is None:
            raise NotFoundError(f"피드백 {feedback_id} 없음")
        return fb

    def search(self, **filters) -> list[Feedback]:
        return self.feedbacks.search(**filters)

    @staticmethod
    def tags_for(fb: Feedback) -> list[str]:
        return decorate(fb.priority, fb.grade).tags()

    def batch_status(self, batch_id: int) -> tuple[UploadBatch, int]:
        b = self.batches.get(batch_id)
        if b is None:
            raise NotFoundError(f"업로드 배치 {batch_id} 없음")
        return b, self.batches.analyzed_count(batch_id)

    # ---------- 상태 (State 패턴 위임 + 이력 기록) ----------
    def change_status(self, feedback_id: int, action: str, user: User) -> Feedback:
        fb = self.get(feedback_id)
        before, after = apply_transition(fb, action)  # InvalidTransitionError 전파
        self.histories.add(StatusHistory(feedback=fb, from_status=before, to_status=after, changed_by=user.id))
        self.db.commit()
        return fb

    # ---------- 정답 라벨 (S07 표본) ----------
    def set_gold_label(self, feedback_id: int, label: str, topic: str, user: User) -> GoldLabel:
        self.get(feedback_id)
        g = GoldLabelRepository(self.db).upsert(feedback_id, label, topic, user.id)
        self.db.commit()
        return g
