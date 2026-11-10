"""DB 엔진/세션 (persistence 계층)."""
from collections.abc import Iterator
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.infra.config import get_settings

_settings = get_settings()
_is_sqlite = _settings.db_url.startswith("sqlite")

engine = create_engine(
    _settings.db_url,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
)

if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn: Any, _record: Any) -> None:
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """테이블 생성 + 초기 데이터 시드."""
    from app.persistence import models  # noqa: F401 - 매핑 등록
    from app.persistence.seed import seed_initial_data

    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_initial_data(db)
