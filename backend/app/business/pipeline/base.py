"""분석 파이프라인 (Pipe-Filter 패턴)."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

from app.persistence.models import Feedback, PriorityScore, SentimentResult


@dataclass
class FeedbackContext:
    """Pipe-Filter 패턴의 Pipe 로 흐르는 데이터."""
    feedback: Feedback
    now: datetime = field(default_factory=datetime.now)
    clean_text: str = ""
    sentiment: SentimentResult | None = None
    topics: list[str] = field(default_factory=list)
    topic_scores: dict[str, float] = field(default_factory=dict)
    priority: PriorityScore | None = None
    tags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)  # 대체 분석 등 처리 기록


class PipelineAbort(Exception):
    """필터가 처리를 중단시킬 때(예: 검증 실패)."""


class Filter(ABC):
    """Pipe-Filter 패턴의 Filter 인터페이스."""

    @abstractmethod
    def process(self, ctx: FeedbackContext) -> FeedbackContext: ...


class Pipeline:
    """Filter 들을 순서대로 실행한다."""

    def __init__(self, filters: list[Filter]):
        self.filters = list(filters)

    def run(self, ctx: FeedbackContext) -> FeedbackContext:
        for f in self.filters:
            ctx = f.process(ctx)
        return ctx
