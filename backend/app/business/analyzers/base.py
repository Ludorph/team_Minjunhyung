"""감정 분석기 인터페이스 (Strategy 패턴의 Strategy)."""
from abc import ABC, abstractmethod

from app.persistence.models import SentimentResult


class SentimentAnalyzer(ABC):
    """Strategy 패턴의 Strategy: 텍스트 → SentimentResult."""

    @abstractmethod
    def analyze(self, text: str) -> SentimentResult: ...
