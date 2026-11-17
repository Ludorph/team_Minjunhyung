"""감정 분석기 인터페이스 (Strategy 패턴의 Strategy)."""
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.persistence.models import SentimentResult


@dataclass
class AnalysisOutcome:
    """분석 결과. topic_scores 는 분석기가 주제까지 판정했을 때만 채운다 (None 이면 키워드 분류기가 판정)."""
    sentiment: SentimentResult
    topic_scores: dict[str, float] | None = None


class SentimentAnalyzer(ABC):
    """Strategy 패턴의 Strategy: 텍스트 → SentimentResult."""

    @abstractmethod
    def analyze(self, text: str) -> SentimentResult: ...

    def analyze_full(self, text: str) -> AnalysisOutcome:
        """감정 + (가능하면) 주제. 기본 구현은 감정만 판정한다."""
        return AnalysisOutcome(self.analyze(text))
