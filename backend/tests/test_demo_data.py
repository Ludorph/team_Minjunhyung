from datetime import datetime

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.business.services.demo_data import load_demo_feedback, shift_to_recent
from app.persistence import models  # noqa: F401 - 매핑 등록
from app.persistence.database import Base
from app.persistence.models import Feedback, PriorityScore
from app.persistence.seed import seed_initial_data

CSV = "customer_name,grade,source,written_at,content\nA,VIP,REVIEW,2026-01-01 10:00,x\nB,NEW,EMAIL,2026-01-02 10:00,y\n"


def _fresh_session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    seed_initial_data(db)
    return db


def test_shift_to_recent_keeps_gaps_and_ends_one_hour_ago():
    out = shift_to_recent(CSV, datetime(2026, 11, 10, 12, 0))
    assert "2026-11-09 11:00" in out and "2026-11-10 11:00" in out  # 간격 24시간 유지, 최신 = now - 1h


def test_load_demo_feedback_loads_once_and_analyzes():
    db = _fresh_session()
    assert load_demo_feedback(db, now=datetime(2026, 11, 10, 12, 0)) == 20
    assert db.scalar(select(func.count()).select_from(PriorityScore)) == 20  # 모두 분석·점수 산정
    assert load_demo_feedback(db) == 0  # 이미 데이터가 있으면 다시 넣지 않음
    assert db.scalar(select(func.count()).select_from(Feedback)) == 20
