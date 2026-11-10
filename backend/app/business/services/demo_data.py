"""배포 시연용 데모 데이터 적재.

FEEDBACKCARE_DEMO_DATA=1 인 환경(공개 데모 서버)에서 DB가 비어 있으면 가상 피드백 CSV를 넣고 분석한다.
작성일은 적재 시각 기준 최근으로 옮겨, 시간 가중치(경과 시간)가 시연할 때마다 의미 있게 나오도록 한다.
"""
import csv
import io
import logging
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.business.services.analysis_service import AnalysisService
from app.business.services.feedback_service import FeedbackService, parse_datetime
from app.infra.config import get_settings
from app.persistence.models import Feedback, User

log = logging.getLogger(__name__)

DEMO_FILE = "sample_feedback.csv"
DEMO_UPLOADER = "agent1"
LATEST_AGE = timedelta(hours=1)  # 가장 최근 피드백이 적재 시각보다 이만큼 이전이 되도록


def shift_to_recent(raw_csv: str, now: datetime) -> str:
    """각 행의 간격은 유지한 채, 가장 최근 written_at 이 now - 1시간이 되도록 날짜를 옮긴다."""
    rows = list(csv.DictReader(io.StringIO(raw_csv)))
    if not rows:
        return raw_csv
    dates = [parse_datetime(r["written_at"]) for r in rows]
    offset = (now - LATEST_AGE) - max(dates)
    for r, d in zip(rows, dates):
        r["written_at"] = (d + offset).strftime("%Y-%m-%d %H:%M")
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(rows[0].keys()), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def load_demo_feedback(db: Session, now: datetime | None = None) -> int:
    """DB에 피드백이 없을 때만 데모 CSV를 적재·분석하고 적재 건수를 반환한다 (멱등)."""
    if db.scalar(select(func.count()).select_from(Feedback)):
        return 0
    path = get_settings().data_dir / DEMO_FILE
    uploader = db.scalar(select(User).where(User.login_id == DEMO_UPLOADER))
    if not path.exists() or uploader is None:
        log.warning("데모 데이터를 적재하지 않음: 파일 또는 업로더 계정 없음 (%s)", path)
        return 0
    raw = shift_to_recent(path.read_text(encoding="utf-8-sig"), now or datetime.now())
    outcome = FeedbackService(db).upload(DEMO_FILE, raw.encode("utf-8"), uploader)
    analyzed = AnalysisService(db).analyze_many(outcome.feedback_ids)
    log.info("데모 데이터 적재: %d건 저장, %d건 분석", len(outcome.feedback_ids), analyzed)
    return len(outcome.feedback_ids)
