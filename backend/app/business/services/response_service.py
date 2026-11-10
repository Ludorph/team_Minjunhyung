"""답변 초안 생성·수정·확정 (UC-04)."""
from sqlalchemy.orm import Session

from app.business.pipeline.base import FeedbackContext
from app.business.response.strategies import StrategySelector
from app.business.services.analysis_service import AnalysisService
from app.business.services.feedback_service import NotFoundError
from app.infra.ai_client import AIClient, ExternalLLMAdapter
from app.persistence.models import ResponseDraft, User
from app.persistence.repositories import FeedbackRepository, ResponseDraftRepository


class ResponseService:
    def __init__(self, db: Session, ai_client: AIClient | None = None):
        self.db = db
        self.ai_client = ai_client or ExternalLLMAdapter()
        self.selector = StrategySelector(self.ai_client)
        self.feedbacks = FeedbackRepository(db)
        self.drafts = ResponseDraftRepository(db)

    def create_draft(self, feedback_id: int, strategy: str | None = None) -> ResponseDraft:
        fb = self.feedbacks.get(feedback_id)
        if fb is None:
            raise NotFoundError(f"피드백 {feedback_id} 없음")
        if fb.sentiment is None:  # 아직 분석 전이면 동기 분석
            AnalysisService(self.db, self.ai_client).analyze(feedback_id)
            self.db.refresh(fb)
        ctx = FeedbackContext(feedback=fb, clean_text=fb.content, sentiment=fb.sentiment,
                              topics=fb.topic_names, priority=fb.priority)
        chosen = self.selector.by_code(strategy) if strategy else self.selector.select(ctx.sentiment, ctx.topics)
        content = chosen.generate(fb, ctx)
        draft = self.drafts.add(ResponseDraft(feedback_id=fb.id, strategy=chosen.code, draft_content=content,
                                              is_ai_generated=chosen.used_ai, confirmed=False))
        self.db.commit()
        return draft

    def _get(self, draft_id: int) -> ResponseDraft:
        d = self.drafts.get(draft_id)
        if d is None:
            raise NotFoundError(f"초안 {draft_id} 없음")
        return d

    def edit(self, draft_id: int, text: str) -> ResponseDraft:
        d = self._get(draft_id)
        d.edit(text)
        self.db.commit()
        return d

    def confirm(self, draft_id: int, text: str | None, user: User) -> ResponseDraft:
        d = self._get(draft_id)
        if text:
            d.edit(text)
        d.confirm(user)
        self.db.commit()
        return d
