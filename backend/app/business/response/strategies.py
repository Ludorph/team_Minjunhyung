"""답변 초안 생성 (Strategy 패턴).

각 전략은 AIClient 로 초안을 생성하고, AI 사용 불가 시 템플릿으로 대체(fallback)한다.
"""
import logging
from abc import ABC, abstractmethod

from app.business.pipeline.base import FeedbackContext
from app.infra.ai_client import AIClient
from app.persistence.models import Feedback, SentimentLabel, SentimentResult

log = logging.getLogger(__name__)


class ResponseStrategy(ABC):
    """Strategy 패턴의 Strategy: 피드백 → 답변 초안 텍스트."""

    code: str = ""
    instruction: str = ""

    def __init__(self, ai_client: AIClient | None = None):
        self.ai_client = ai_client

    used_ai: bool = False  # 마지막 generate() 결과가 AI 생성인지(템플릿 대체면 False)

    def generate(self, fb: Feedback, ctx: FeedbackContext) -> str:
        if self.ai_client is not None:
            try:
                text = self.ai_client.complete(self._prompt(fb, ctx))
                self.used_ai = True
                return text
            except Exception as e:  # noqa: BLE001
                log.info("AI 초안 생성 실패 → 템플릿 사용: %s", e)
        self.used_ai = False
        return self.template(fb, ctx)

    def _prompt(self, fb: Feedback, ctx: FeedbackContext) -> str:
        return (f"당신은 중소기업 고객 응대 담당자입니다. {self.instruction}\n"
                f"주제: {', '.join(ctx.topics) or '기타'}\n고객 피드백: {fb.content}")

    @staticmethod
    def _name(fb: Feedback) -> str:
        return f"{fb.customer.name} 고객님" if fb.customer else "고객님"

    @abstractmethod
    def template(self, fb: Feedback, ctx: FeedbackContext) -> str:
        """AI 미사용 시 템플릿 기반 초안."""


class ApologyStrategy(ResponseStrategy):
    """Strategy 패턴의 ConcreteStrategy: 사과형 (부정 피드백)."""
    code = "APOLOGY"
    instruction = "불편을 겪은 고객에게 정중히 사과하고 조치 계획을 안내하는 답변을 작성하세요."

    def template(self, fb: Feedback, ctx: FeedbackContext) -> str:
        topic = ctx.topics[0] if ctx.topics else "이용"
        return (f"{self._name(fb)}, 먼저 {topic} 관련하여 불편을 드려 진심으로 사과드립니다. "
                "말씀해 주신 내용을 담당 부서와 확인하여 빠르게 조치하고 결과를 안내드리겠습니다. "
                "소중한 의견 감사합니다.")


class GuidanceStrategy(ResponseStrategy):
    """Strategy 패턴의 ConcreteStrategy: 안내형 (중립·문의성 피드백)."""
    code = "GUIDANCE"
    instruction = "고객의 문의에 필요한 정보를 명확하게 안내하는 답변을 작성하세요."

    def template(self, fb: Feedback, ctx: FeedbackContext) -> str:
        topic = ctx.topics[0] if ctx.topics else "문의"
        return (f"{self._name(fb)}, {topic} 관련 문의 주셔서 감사합니다. "
                "확인 후 자세한 내용을 안내드리겠으며, 추가로 궁금하신 점은 고객센터로 언제든 문의해 주세요.")


class ThanksStrategy(ResponseStrategy):
    """Strategy 패턴의 ConcreteStrategy: 감사형 (긍정 피드백)."""
    code = "THANKS"
    instruction = "긍정적인 의견을 남긴 고객에게 감사를 전하는 답변을 작성하세요."

    def template(self, fb: Feedback, ctx: FeedbackContext) -> str:
        return (f"{self._name(fb)}, 좋은 말씀 남겨 주셔서 진심으로 감사드립니다. "
                "앞으로도 만족하실 수 있도록 더욱 노력하겠습니다.")


STRATEGIES: dict[str, type[ResponseStrategy]] = {
    s.code: s for s in (ApologyStrategy, GuidanceStrategy, ThanksStrategy)
}


class StrategySelector:
    """감정·주제에 따라 ResponseStrategy 를 선택한다 (Strategy 패턴의 Context 역할 보조)."""

    def __init__(self, ai_client: AIClient | None = None):
        self.ai_client = ai_client

    def select(self, sentiment: SentimentResult | None, topics: list[str]) -> ResponseStrategy:
        label = sentiment.label if sentiment else SentimentLabel.NEUTRAL
        if label == SentimentLabel.NEGATIVE:
            return ApologyStrategy(self.ai_client)
        if label == SentimentLabel.POSITIVE:
            return ThanksStrategy(self.ai_client)
        return GuidanceStrategy(self.ai_client)

    def by_code(self, code: str) -> ResponseStrategy:
        try:
            return STRATEGIES[code.upper()](self.ai_client)
        except KeyError:
            raise ValueError(f"알 수 없는 답변 전략: {code} (가능: {', '.join(STRATEGIES)})") from None
