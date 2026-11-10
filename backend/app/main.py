"""FastAPI 진입점. 실행: (backend 폴더에서) uvicorn app.main:app --reload"""
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.persistence.database import init_db
from app.presentation.routers import auth, dashboard, drafts, feedbacks

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_db()  # 테이블 생성 + grade_weights/topics/users 시드
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
