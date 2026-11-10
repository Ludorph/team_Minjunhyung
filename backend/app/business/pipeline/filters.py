"""Pipe-Filter 패턴의 ConcreteFilter 들: Validation → Cleansing → Sentiment → Topic → Priority."""
import logging
import re

from app.business.analyzers.base import SentimentAnalyzer
from app.business.analyzers.topic_classifier import TopicClassifier
from app.business.pipeline.base import FeedbackContext, Filter, PipelineAbortError
from app.business.priority.calculator import PriorityCalculator
from app.business.priority.decorators import decorate
from app.persistence.models import SentimentLabel

log = logging.getLogger(__name__)


class ValidationFilter(Filter):
    """ConcreteFilter: 내용 유효성 검사."""

    def __init__(self, max_length: int = 5000):
        self.max_length = max_length

    def process(self, ctx: FeedbackContext) -> FeedbackContext:
        content = (ctx.feedback.content or "").strip()
        if not content:
            raise PipelineAbortError("내용이 비어 있습니다.")
        if len(content) > self.max_length:
            raise PipelineAbortError(f"내용이 너무 깁니다({len(content)}자).")
        return ctx


class CleansingFilter(Filter):
    """ConcreteFilter: 공백 정리, URL 제거, 개인정보(전화번호·이메일) 마스킹."""

    _url = re.compile(r"https?://\S+")
    _phone = re.compile(r"01[016789]-?\d{3,4}-?\d{4}")
    _email = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")

    def process(self, ctx: FeedbackContext) -> FeedbackContext:
        t = self._url.sub(" ", ctx.feedback.content)
        t = self._phone.sub("[전화번호]", t)
        t = self._email.sub("[이메일]", t)
        ctx.clean_text = re.sub(r"\s+", " ", t).strip()
        return ctx


class SentimentFilter(Filter):
    """ConcreteFilter: primary(LLM) 분석, 실패 시 fallback(규칙 기반)으로 대체."""

    def __init__(self, primary: SentimentAnalyzer, fallback: SentimentAnalyzer):
        self.primary = primary
        self.fallback = fallback

    def process(self, ctx: FeedbackContext) -> FeedbackContext:
        try:
            ctx.sentiment = self.primary.analyze(ctx.clean_text)
        except Exception as e:  # noqa: BLE001 - AI 장애·타임아웃 등 (E1)
            log.info("primary 분석 실패 → 규칙 기반 대체: %s", e)
            ctx.notes.append(f"fallback: {e}")
            ctx.sentiment = self.fallback.analyze(ctx.clean_text)
        return ctx


class TopicFilter(Filter):
    """ConcreteFilter: 주제 분류."""

    def __init__(self, classifier: TopicClassifier):
        self.classifier = classifier

    def process(self, ctx: FeedbackContext) -> FeedbackContext:
        ctx.topic_scores = self.classifier.classify(ctx.clean_text)
        ctx.topics = list(ctx.topic_scores)
        return ctx


class PriorityFilter(Filter):
    """ConcreteFilter: 우선순위 산출 + 태그 Decorator 적용."""

    def __init__(self, calculator: PriorityCalculator):
        self.calculator = calculator

    def process(self, ctx: FeedbackContext) -> FeedbackContext:
        s = ctx.sentiment
        neg = float(s.intensity) if s is not None and s.label == SentimentLabel.NEGATIVE else 0.0
        grade = ctx.feedback.grade
        ctx.priority = self.calculator.calculate(neg, grade, ctx.feedback.elapsed_hours(ctx.now))
        ctx.tags = decorate(ctx.priority, grade).tags()
        return ctx
