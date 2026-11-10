import json

from app.business.analyzers.base import SentimentAnalyzer
from app.infra.ai_client import AIClient, AIClientError
from app.persistence.models import SentimentLabel, SentimentResult

PROMPT = (
    "다음 고객 피드백의 감정을 분석해 JSON 으로만 답하세요. "
    '형식: {{"label": "POSITIVE|NEUTRAL|NEGATIVE", "intensity": 0~1, "confidence": 0~1}}\n'
    "피드백: {text}"
)


class LLMSentimentAnalyzer(SentimentAnalyzer):
    """Strategy 패턴의 ConcreteStrategy: 외부 LLM(AIClient)으로 분석. 실패 시 AIClientError."""

    def __init__(self, client: AIClient):
        self.client = client

    def analyze(self, text: str) -> SentimentResult:
        raw = self.client.complete(PROMPT.format(text=text))
        try:
            data = json.loads(raw)
            label = str(data["label"]).upper()
            if label not in SentimentLabel.ALL:
                raise ValueError(label)
            return SentimentResult(
                label=label,
                intensity=min(max(float(data["intensity"]), 0.0), 1.0),
                confidence=min(max(float(data.get("confidence", 0.8)), 0.0), 1.0),
                analyzer="LLM",
            )
        except (ValueError, KeyError, TypeError) as e:
            raise AIClientError(f"LLM 응답 형식 오류: {raw!r}") from e
