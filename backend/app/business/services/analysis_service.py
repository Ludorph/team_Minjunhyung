"""분석 서비스: 파이프라인을 조립·실행하고 결과를 저장한다 (UC-02, UC-03)."""
import logging

from sqlalchemy.orm import Session

from app.business.analyzers.llm_analyzer import LLMSentimentAnalyzer
from app.business.analyzers.rule_based_analyzer import RuleBasedSentimentAnalyzer
from app.business.analyzers.topic_classifier import TopicClassifier
from app.business.pipeline.base import FeedbackContext, Pipeline, PipelineAbortError
from app.business.pipeline.filters import (
    CleansingFilter,
    PriorityFilter,
    SentimentFilter,
    TopicFilter,
    ValidationFilter,
)
from app.business.priority.calculator import PriorityCalculator
from app.infra.ai_client import AIClient, ExternalLLMAdapter
from app.persistence.database import SessionLocal
from app.persistence.models import Feedback, FeedbackTopic
from app.persistence.repositories import FeedbackRepository, GradeWeightRepository, TopicRepository

log = logging.getLogger(__name__)


class AnalysisService:
    def __init__(self, db: Session, ai_client: AIClient | None = None):
        self.db = db
        self.ai_client = ai_client or ExternalLLMAdapter()
        self.feedbacks = FeedbackRepository(db)

    def build_pipeline(self) -> Pipeline:
        calculator = PriorityCalculator(GradeWeightRepository(self.db).as_dict())
        return Pipeline([
            ValidationFilter(),
            CleansingFilter(),
            SentimentFilter(primary=LLMSentimentAnalyzer(self.ai_client),
                            fallback=RuleBasedSentimentAnalyzer()),
            TopicFilter(TopicClassifier()),
            PriorityFilter(calculator),
        ])

    def analyze(self, feedback_id: int, pipeline: Pipeline | None = None) -> FeedbackContext | None:
        fb = self.feedbacks.get(feedback_id)
        if fb is None:
            return None
        try:
            ctx = (pipeline or self.build_pipeline()).run(FeedbackContext(feedback=fb))
        except PipelineAbortError as e:
            log.warning("피드백 %s 분석 중단: %s", feedback_id, e)
            return None
        self._save(fb, ctx)
        self.db.commit()
        return ctx

    def analyze_many(self, feedback_ids: list[int]) -> int:
        pipeline = self.build_pipeline()
        return sum(1 for fid in feedback_ids if self.analyze(fid, pipeline) is not None)

    def _save(self, fb: Feedback, ctx: FeedbackContext) -> None:
        # 재분석 시 기존 결과 제거 후 저장 (PK 충돌 방지를 위해 flush)
        if fb.sentiment is not None or fb.priority is not None or fb.topic_links:
            fb.sentiment = None
            fb.priority = None
            fb.topic_links.clear()
            self.db.flush()
        fb.sentiment = ctx.sentiment
        fb.priority = ctx.priority
        topics = TopicRepository(self.db).by_name()
        for name, score in ctx.topic_scores.items():
            topic = topics.get(name) or topics["기타"]
            if all(link.topic_id != topic.id for link in fb.topic_links):
                fb.topic_links.append(FeedbackTopic(topic=topic, topic_id=topic.id, score=score))


def run_analysis_task(feedback_ids: list[int]) -> None:
    """FastAPI BackgroundTasks 진입점: 요청과 별도 세션으로 실행한다."""
    with SessionLocal() as db:
        n = AnalysisService(db).analyze_many(feedback_ids)
        log.info("백그라운드 분석 완료: %d/%d", n, len(feedback_ids))
