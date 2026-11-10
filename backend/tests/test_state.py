from datetime import datetime

import pytest

from app.business.services.feedback_service import FeedbackService
from app.business.state.feedback_state import InvalidTransitionError, apply_transition, state_of
from app.persistence.models import Feedback, ResponseDraft, User


def _fb(status="PENDING", confirmed_draft=False):
    fb = Feedback(content="테스트", source="REVIEW", written_at=datetime.now(), status=status)
    if confirmed_draft:
        fb.drafts.append(ResponseDraft(strategy="APOLOGY", draft_content="초안", confirmed=True))
    return fb


def test_happy_path():
    fb = _fb()
    assert apply_transition(fb, "start") == ("PENDING", "IN_PROGRESS")
    fb.drafts.append(ResponseDraft(strategy="THANKS", draft_content="x", confirmed=True))
    assert apply_transition(fb, "complete") == ("IN_PROGRESS", "DONE")
    assert apply_transition(fb, "reopen") == ("DONE", "IN_PROGRESS")
    assert state_of(fb).label == "처리중"


@pytest.mark.parametrize("status,action", [
    ("PENDING", "complete"), ("PENDING", "reopen"),
    ("IN_PROGRESS", "start"), ("IN_PROGRESS", "reopen"),
    ("DONE", "start"), ("DONE", "complete"),
])
def test_invalid_transitions(status, action):
    fb = _fb(status, confirmed_draft=True)
    with pytest.raises(InvalidTransitionError):
        apply_transition(fb, action)
    assert fb.status == status  # 상태 불변


def test_complete_requires_confirmed_draft():
    fb = _fb("IN_PROGRESS")
    fb.drafts.append(ResponseDraft(strategy="APOLOGY", draft_content="미확정", confirmed=False))
    with pytest.raises(InvalidTransitionError):
        apply_transition(fb, "complete")


def test_service_writes_status_history(db):
    user = db.query(User).filter_by(login_id="agent1").one()
    svc = FeedbackService(db)
    fb = svc.create("상태 이력 테스트", "EMAIL", None, None, None)
    svc.change_status(fb.id, "start", user)
    with pytest.raises(InvalidTransitionError):
        svc.change_status(fb.id, "complete", user)  # 확정 초안 없음
    db.rollback()
    db.refresh(fb)
    assert fb.status == "IN_PROGRESS"
    assert [(h.from_status, h.to_status, h.changed_by) for h in fb.histories] == \
        [("PENDING", "IN_PROGRESS", user.id)]
