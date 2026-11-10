"""환경 설정 (infra 계층). 환경변수로 덮어쓸 수 있다."""
import os
from dataclasses import dataclass
from pathlib import Path

# backend/ 디렉터리
BASE_DIR = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    db_url: str
    ai_api_key: str | None
    ai_endpoint: str | None
    ai_timeout: float


def get_settings() -> Settings:
    return Settings(
        db_url=os.getenv("FEEDBACKCARE_DB_URL", f"sqlite:///{(BASE_DIR / 'feedbackcare.db').as_posix()}"),
        ai_api_key=os.getenv("FEEDBACKCARE_AI_API_KEY") or None,
        ai_endpoint=os.getenv("FEEDBACKCARE_AI_ENDPOINT") or None,
        ai_timeout=float(os.getenv("FEEDBACKCARE_AI_TIMEOUT", "5")),
    )
