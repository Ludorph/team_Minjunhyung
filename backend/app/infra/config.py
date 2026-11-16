"""환경 설정 (infra 계층). 환경변수로 덮어쓸 수 있다."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# backend/ 디렉터리
BASE_DIR = Path(__file__).resolve().parents[2]
# 로컬 개발용 backend/.env (커밋 금지). 이미 설정된 환경변수(배포 서비스·테스트)가 우선한다.
load_dotenv(BASE_DIR / ".env", override=False)


@dataclass(frozen=True)
class Settings:
    db_url: str
    ai_api_key: str | None  # Claude API 키. 없으면 규칙 기반·템플릿으로 대체 (NFR-03)
    ai_model: str
    ai_effort: str  # Claude 사고 깊이 (low/medium/high). 5초 안에 답하도록 기본 low
    ai_timeout: float
    demo_data: bool  # 배포 시연용: DB가 비어 있으면 가상 피드백을 자동 적재
    frontend_dist: Path  # 빌드된 React 화면 폴더 (있으면 백엔드가 함께 제공)
    data_dir: Path


def get_settings() -> Settings:
    return Settings(
        db_url=os.getenv("FEEDBACKCARE_DB_URL", f"sqlite:///{(BASE_DIR / 'feedbackcare.db').as_posix()}"),
        ai_api_key=os.getenv("FEEDBACKCARE_AI_API_KEY") or None,
        ai_model=os.getenv("FEEDBACKCARE_AI_MODEL", "claude-opus-5-5"),
        ai_effort=os.getenv("FEEDBACKCARE_AI_EFFORT", "low"),
        ai_timeout=float(os.getenv("FEEDBACKCARE_AI_TIMEOUT", "5")),
        demo_data=os.getenv("FEEDBACKCARE_DEMO_DATA", "").lower() in ("1", "true", "yes"),
        frontend_dist=Path(os.getenv("FEEDBACKCARE_FRONTEND_DIST", str(BASE_DIR.parent / "frontend" / "dist"))),
        data_dir=BASE_DIR.parent / "data",
    )
