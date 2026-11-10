"""피드백 처리 상태 (State 패턴, 08_state_machine.puml).

PENDING(미처리) -start-> IN_PROGRESS(처리중) -complete-> DONE(완료) -reopen-> IN_PROGRESS
그 외 전이는 InvalidTransitionError. 이력(status_histories) 기록은 FeedbackService 가 담당한다.
"""
from abc import ABC

from app.persistence.models import Feedback

STATUS_LABELS = {"PENDING": "미처리", "IN_PROGRESS": "처리중", "DONE": "완료"}
ACTION_LABELS = {"start": "처리 시작", "complete": "완료", "reopen": "재오픈"}


class InvalidTransitionError(Exception):
    """허용되지 않는 상태 전이."""


class FeedbackState(ABC):
    """State 패턴의 State(추상). 기본 구현은 모든 전이를 거부한다."""

    name: str = ""

    @property
    def label(self) -> str:
        return STATUS_LABELS[self.name]

    def start(self, fb: Feedback) -> None:
        self._reject("start")

    def complete(self, fb: Feedback) -> None:
        self._reject("complete")

    def reopen(self, fb: Feedback) -> None:
        self._reject("reopen")

    def _reject(self, action: str):
        raise InvalidTransitionError(
            f"'{self.label}' 상태에서는 '{ACTION_LABELS[action]}' 전이를 할 수 없습니다.")

    @staticmethod
    def _move(fb: Feedback, target: "FeedbackState") -> None:
        fb.status = target.name


class PendingState(FeedbackState):
    """State 패턴의 ConcreteState: 미처리."""
    name = "PENDING"

    def start(self, fb: Feedback) -> None:
        self._move(fb, IN_PROGRESS)


class InProgressState(FeedbackState):
    """State 패턴의 ConcreteState: 처리중. 확정된 답변이 있어야 완료 가능."""
    name = "IN_PROGRESS"

    def complete(self, fb: Feedback) -> None:
        if not any(d.confirmed for d in fb.drafts):
            raise InvalidTransitionError("확정된 답변 초안이 없어 완료 처리할 수 없습니다.")
        self._move(fb, DONE)


class DoneState(FeedbackState):
    """State 패턴의 ConcreteState: 완료."""
    name = "DONE"

    def reopen(self, fb: Feedback) -> None:
        self._move(fb, IN_PROGRESS)


PENDING, IN_PROGRESS, DONE = PendingState(), InProgressState(), DoneState()
_STATES = {s.name: s for s in (PENDING, IN_PROGRESS, DONE)}


def state_of(fb: Feedback) -> FeedbackState:
    """Context(Feedback)의 status 문자열에서 현재 State 객체를 얻는다."""
    return _STATES[fb.status]


def apply_transition(fb: Feedback, action: str) -> tuple[str, str]:
    """action(start/complete/reopen)을 현재 상태에 위임하고 (이전, 이후) 상태를 반환."""
    if action not in ACTION_LABELS:
        raise InvalidTransitionError(f"알 수 없는 전이: {action}")
    before = fb.status
    getattr(state_of(fb), action)(fb)
    return before, fb.status
