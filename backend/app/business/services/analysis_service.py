"""분석 서비스: 파이프라인을 조립·실행하고 결과를 저장한다 (UC-02, UC-03)."""
import logging
from concurrent.futures import ThreadPoolExecutor

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
from app.infra.config import get_settings
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


def _analyze_chunk(feedback_ids: list[int], ai_client: AIClient | None) -> int:
    """작업 하나가 자기 DB 세션으로 담당 구간을 순서대로 분석한다 (세션은 스레드 간에 공유하지 않는다)."""
    with SessionLocal() as db:
        return AnalysisService(db, ai_client).analyze_many(feedback_ids)


def run_analysis_task(feedback_ids: list[int], ai_client: AIClient | None = None) -> None:
    """FastAPI BackgroundTasks 진입점: 요청과 별도 세션으로 실행한다.

    AI 응답을 기다리는 시간이 건당 1~2초라 순서대로 처리하면 500건에 10분이 넘는다(NFR-02: 5분).
    그래서 여러 작업이 구간을 나눠 동시에 처리해 대기 시간을 겹친다. 실패는 건별로 규칙 기반으로 대체된다.
    """
    workers = min(get_settings().analysis_workers, len(feedback_ids))
    if workers <= 1:
        done = _analyze_chunk(feedback_ids, ai_client)
    else:
        chunks = [feedback_ids[i::workers] for i in range(workers)]
        with ThreadPoolExecutor(max_workers=workers) as pool:
            done = sum(pool.map(lambda c: _analyze_chunk(c, ai_client), chunks))
    log.info("백그라운드 분석 완료: %d/%d (작업 %d개)", done, len(feedback_ids), max(workers, 1))
