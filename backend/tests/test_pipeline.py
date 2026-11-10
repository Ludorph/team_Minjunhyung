from datetime import datetime, timedelta

from app.business.analyzers.rule_based_analyzer import RuleBasedSentimentAnalyzer
from app.business.pipeline.base import FeedbackContext
from app.business.services.analysis_service import AnalysisService
from app.business.services.response_service import ResponseService
from app.infra.ai_client import AIClient, ExternalLLMAdapter
from app.persistence.models import Customer, Feedback


class FakeLLM(AIClient):
    """정상 동작하는 AI 를 흉내내는 테스트 더블."""

    def complete(self, prompt: str) -> str:
        return '{"label": "NEGATIVE", "intensity": 0.9, "confidence": 0.95}'


def test_rule_based_lexicon():
    a = RuleBasedSentimentAnalyzer()
    assert a.analyze("정말 만족합니다. 감사합니다").label == "POSITIVE"
    assert a.analyze("직원이 불친절해서 실망했어요").label == "NEGATIVE"  # '불친절'이 '친절'보다 우선
    assert a.analyze("설명서대로 사용 중입니다").label == "NEUTRAL"


def test_pipeline_end_to_end_with_fallback(db):
    """AI 키가 없으면 ExternalLLMAdapter 가 실패 → SentimentFilter 가 규칙 기반으로 대체."""
    customer = Customer(name="테스트VIP", grade="VIP")
    fb = Feedback(content="  배송이 늦고 상품이 파손되어 너무 실망했습니다. 최악이에요!  010-1234-5678 ",
                  source="REVIEW", written_at=datetime.now() - timedelta(hours=80),
                  customer=customer, status="PENDING")
    db.add(fb)
    db.commit()

    svc = AnalysisService(db, ExternalLLMAdapter(api_key=None))
    ctx = svc.analyze(fb.id)
    assert isinstance(ctx, FeedbackContext)
    assert "[전화번호]" in ctx.clean_text and not ctx.clean_text.startswith(" ")
    assert ctx.notes and ctx.notes[0].startswith("fallback")
    assert ctx.sentiment.analyzer == "RULE"
    assert ctx.sentiment.label == "NEGATIVE"
    assert "배송" in ctx.topics and "품질" in ctx.topics
    assert ctx.priority.time_weight == 2.0 and ctx.priority.grade_weight == 1.5
    assert ctx.priority.is_urgent
    assert ctx.tags == ["긴급", "VIP"]

    db.refresh(fb)
    assert fb.sentiment.analyzer == "RULE"
    assert fb.priority.is_urgent is True
    assert set(fb.topic_names) >= {"배송", "품질"}

    # 재분석(LLM 정상) 시 결과 교체
    ctx2 = AnalysisService(db, FakeLLM()).analyze(fb.id)
    assert ctx2.sentiment.analyzer == "LLM" and not ctx2.notes
    db.refresh(fb)
    assert fb.sentiment.analyzer == "LLM"
    assert fb.priority.score == 27.0  # 0.9×10×1.5×2.0


def test_draft_marks_ai_generated(db):
    """AI 가 정상 응답하면 초안을 AI 생성으로 기록한다 (운영계획서 13절 AI 생성 표시)."""
    fb = Feedback(content="상품이 불량이라 실망했습니다", source="EMAIL", written_at=datetime.now(), status="PENDING")
    db.add(fb)
    db.commit()
    draft = ResponseService(db, FakeLLM()).create_draft(fb.id)
    assert draft.is_ai_generated is True and draft.is_edited is False


def test_validation_filter_aborts_empty(db):
    fb = Feedback(content="   ", source="REVIEW", written_at=datetime.now(), status="PENDING")
    db.add(fb)
    db.commit()
    assert AnalysisService(db).analyze(fb.id) is None
