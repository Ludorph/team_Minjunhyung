"""Claude Adapter·LLM 분석기 테스트.

실제 API 를 부르지 않고 SDK 클라이언트를 가짜로 바꿔 요청 형식과 실패 처리를 확인한다.
"""
import json
from datetime import datetime
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from app.business.analyzers.llm_analyzer import SCHEMA, LLMSentimentAnalyzer
from app.business.services.analysis_service import AnalysisService
from app.business.services.response_service import ResponseService
from app.infra.ai_client import AIClient, AIClientError, ExternalLLMAdapter
from app.persistence.models import Customer, Feedback


def _resp(text: str, stop_reason: str = "end_turn"):
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
        model="claude-opus-5-5",
        usage=SimpleNamespace(input_tokens=100, output_tokens=20),
    )


class FakeAnthropic:
    """anthropic.Anthropic 대역: beta.messages.create 호출 인자를 기록하고 정해 둔 응답/예외를 돌려준다."""

    def __init__(self, resp=None, exc=None):
        self.calls = []
        self._resp, self._exc = resp, exc
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._exc is not None:
            raise self._exc
        return self._resp


def test_no_key_raises_without_calling_api():
    with pytest.raises(AIClientError, match="FEEDBACKCARE_AI_API_KEY"):
        ExternalLLMAdapter(api_key="").complete("안녕")


def test_complete_json_uses_structured_output_and_fallbacks():
    fake = FakeAnthropic(_resp('{"label": "NEGATIVE"}'))
    ai = ExternalLLMAdapter(api_key="test", model="claude-opus-5-5", effort="low", client=fake)
    assert ai.complete_json("<feedback>x</feedback>", SCHEMA, system="분석기") == {"label": "NEGATIVE"}
    call = fake.calls[0]
    assert call["model"] == "claude-opus-5-5" and call["system"] == "분석기"
    assert call["output_config"] == {"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}}
    assert call["fallbacks"] == "default" and call["betas"] == ["server-side-fallback-2026-07-01"]


def test_model_without_server_fallback_sends_no_beta():
    fake = FakeAnthropic(_resp("초안"))
    assert ExternalLLMAdapter(api_key="t", model="claude-haiku-5-5", client=fake).complete("p") == "초안"
    assert "fallbacks" not in fake.calls[0] and "betas" not in fake.calls[0]


@pytest.mark.parametrize("resp, exc, msg", [
    (_resp("", "refusal"), None, "거절"),
    (_resp("{", "max_tokens"), None, "잘렸"),
    (_resp("   "), None, "비어"),
    (None, anthropic.APITimeoutError(request=httpx2.Request("POST", "https://api.anthropic.com")), "시간 초과"),
    (None, anthropic.RateLimitError("rate", response=httpx2.Response(
        429, request=httpx2.Request("POST", "https://api.anthropic.com")), body=None), "한도"),
])
def test_failures_become_ai_client_error(resp, exc, msg):
    """모든 실패는 AIClientError 로 바뀌어 호출 측이 규칙 기반·템플릿으로 대체할 수 있다 (NFR-03)."""
    ai = ExternalLLMAdapter(api_key="t", client=FakeAnthropic(resp, exc))
    with pytest.raises(AIClientError, match=msg):
        ai.complete("p")


class TopicLLM(AIClient):
    """감정·주제를 한 번에 돌려주는 AI 대역. 받은 프롬프트를 기록한다."""

    def __init__(self):
        self.prompts = []

    def complete(self, prompt, system=None):
        self.prompts.append(prompt)
        if "답변 유형" in prompt:
            return "고객님, 불편을 드려 죄송합니다."
        return json.dumps({"label": "NEGATIVE", "intensity": 1.4, "confidence": 0.9,
                           "topics": [{"name": "기타", "score": 0.1}, {"name": "서비스", "score": 0.8}]})


def test_llm_analyzer_returns_sentiment_and_topics_in_one_call():
    llm = TopicLLM()
    out = LLMSentimentAnalyzer(llm).analyze_full("배송 기사님이 너무 불친절했어요")
    assert len(llm.prompts) == 1
    assert out.sentiment.label == "NEGATIVE" and out.sentiment.intensity == 1.0  # 범위 밖 값은 0~1로 자름
    assert out.topic_scores == {"서비스": 0.8}  # 구체 주제가 있으면 '기타' 제외


def test_pipeline_uses_ai_topics_and_masks_pii_for_drafts(db):
    fb = Feedback(content="배송 기사님이 불친절했어요. 연락 주세요 010-1234-5678", source="EMAIL",
                  written_at=datetime.now(), customer=Customer(name="홍길동", grade="VIP"), status="PENDING")
    db.add(fb)
    db.commit()
    llm = TopicLLM()
    ctx = AnalysisService(db, llm).analyze(fb.id)
    assert ctx.topics == ["서비스"]  # 키워드 분류기였다면 '배송'도 나온다 → AI 결과를 그대로 사용
    assert "010-1234-5678" not in llm.prompts[0]

    draft = ResponseService(db, llm).create_draft(fb.id)
    assert draft.is_ai_generated is True
    assert "010-1234-5678" not in llm.prompts[-1] and "[전화번호]" in llm.prompts[-1]
    assert "홍길동" in llm.prompts[-1]
