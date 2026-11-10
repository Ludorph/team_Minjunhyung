"""초기 데이터 시드 (멱등). 앱 시작 시 실행된다."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infra.security import hash_password
from app.persistence.models import GradeWeight, Role, Topic, User

GRADE_WEIGHTS = {"VIP": 1.5, "REGULAR": 1.0, "NEW": 0.8}
TOPICS = ["품질", "배송", "가격", "서비스", "기타"]
USERS = [
    # (login_id, password, name, role) - 과제용 테스트 계정
    ("agent1", "agent1234", "상담원1", Role.AGENT),
    ("admin1", "admin1234", "관리자1", Role.ADMIN),
]


def seed_initial_data(db: Session) -> None:
    for grade, weight in GRADE_WEIGHTS.items():
        if db.get(GradeWeight, grade) is None:
            db.add(GradeWeight(grade=grade, weight=weight))
    existing_topics = set(db.scalars(select(Topic.name)))
    for name in TOPICS:
        if name not in existing_topics:
            db.add(Topic(name=name))
    existing_users = set(db.scalars(select(User.login_id)))
    for login_id, pw, name, role in USERS:
        if login_id not in existing_users:
            db.add(User(login_id=login_id, password_hash=hash_password(pw), name=name, role=role))
    db.commit()
