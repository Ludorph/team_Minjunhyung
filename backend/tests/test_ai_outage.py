"""AI 장애 시 대체 경로 시험 (NFR-03): 응답이 늦다가 시간 초과로 실패해도 분석·초안이 한 건도 빠지지 않는다."""
import time
from datetime import datetime

from app.business.services.analysis_service import AnalysisService, run_analysis_task
from app.business.services.response_service import ResponseService
from app.infra.ai_client import AIClient, AIClientError
from app.persistence.models import Feedback

N = 20


class SlowFailingAI(AIClient):
    """매 호출마다 지연한 뒤 시간 초과로 실패하는 AI 대역 (실제 5초 대신 짧게 주입)."""

    def __init__(self, delay: float = 0.05):
        self.delay = delay
        self.calls = 0

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls += 1
        time.sleep(self.delay)
        raise AIClientError("시간 초과")


def test_all_feedbacks_analyzed_and_drafted_when_ai_times_out(db):
    texts = ["배송이 늦어서 실망했습니다", "품질이 좋아요 감사합니다", "사용법이 궁금합니다"]
    ids = []
    for i in range(N):
        fb = Feedback(content=texts[i % 3], source="REVIEW", written_at=datetime.now(), status="PENDING")
        db.add(fb)
        db.commit()
        ids.append(fb.id)

    ai = SlowFailingAI()
    assert AnalysisService(db, ai).analyze_many(ids) == N  # 누락률 0%
    assert ai.calls >= N  # AI 를 실제로 시도했다 (대체가 아니라 호출 후 실패)
    for fid in ids:
        fb = db.get(Feedback, fid)
        assert fb.sentiment is not None and fb.sentiment.analyzer == "RULE"
        assert fb.priority is not None

    drafts = [ResponseService(db, SlowFailingAI()).create_draft(fid) for fid in ids]
    assert len(drafts) == N and all(d.is_ai_generated is False and d.draft_content for d in drafts)


class SlowOkAI(AIClient):
    """응답이 늦지만 정상인 AI 대역 (일괄 분석의 동시 처리 효과를 보려는 용도)."""

    def complete(self, prompt: str, system: str | None = None) -> str:
        time.sleep(0.2)
        return ('{"label": "NEGATIVE", "intensity": 0.8, "confidence": 0.9, '
                '"topics": [{"name": "배송", "score": 0.9}]}')


def test_bulk_analysis_runs_concurrently(db):
    """AI 응답이 건당 0.2초일 때 40건은 순서대로면 8초, 동시 처리(작업 8개)면 약 1초대에 끝난다."""
    ids = []
    for _ in range(40):
        fb = Feedback(content="배송이 늦어서 실망했습니다", source="REVIEW", status="PENDING",
                      written_at=datetime.now())
        db.add(fb)
        db.commit()
        ids.append(fb.id)
    t0 = time.perf_counter()
    run_analysis_task(ids, SlowOkAI())
    elapsed = time.perf_counter() - t0
    db.expire_all()
    assert all(db.get(Feedback, i).sentiment.analyzer == "LLM" for i in ids)
    assert elapsed < 4.0  # 순서대로(8초)보다 확실히 빠름
