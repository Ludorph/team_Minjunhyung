"""FastAPI 진입점. 실행: (backend 폴더에서) uvicorn app.main:app --reload

배포 시에는 빌드된 React 화면(frontend/dist)도 이 서버가 함께 제공하므로, 주소 하나로 화면과 API를 모두 쓴다.
"""
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.business.services.demo_data import load_demo_feedback
from app.infra.config import get_settings
from app.persistence.database import SessionLocal, init_db
from app.presentation.routers import auth, dashboard, drafts, feedbacks

logging.basicConfig(level=logging.INFO)
settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_db()  # 테이블 생성 + grade_weights/topics/users 시드
    if settings.demo_data:
        with SessionLocal() as db:
            load_demo_feedback(db)
    yield


app = FastAPI(
    title="FeedbackCare - 고객 피드백 감정 분석 및 대응 지원 시스템",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth.router, feedbacks.router, drafts.router, dashboard.router):
    app.include_router(r)


@app.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


# API 라우트를 모두 등록한 뒤 마지막에 화면을 연결해야 /api 경로가 가려지지 않는다
if (settings.frontend_dist / "index.html").exists():
    app.mount("/", StaticFiles(directory=settings.frontend_dist, html=True), name="frontend")
