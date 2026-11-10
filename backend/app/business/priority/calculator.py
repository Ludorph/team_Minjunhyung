"""우선순위 점수 계산.

P = (negIntensity × 10) × gradeWeight × timeWeight
  - negIntensity : 감정이 NEGATIVE 일 때의 강도(0~1), 그 외 0
  - gradeWeight  : grade_weights 테이블 (VIP 1.5 / REGULAR 1.0 / NEW 0.8, 미지정·알 수 없음 1.0)
  - timeWeight   : 1 + min(경과시간, 72) / 72  (1.0 ~ 2.0)
최댓값 30, P ≥ 15 이면 긴급.
"""
from abc import ABC, abstractmethod

from app.persistence.models import PriorityScore

URGENT_THRESHOLD = 15.0
MAX_HOURS = 72.0
DEFAULT_GRADE_WEIGHT = 1.0


class PriorityRule(ABC):
    """Strategy 패턴의 Strategy: 세 요소를 하나의 우선순위 점수(0~30)로 결합한다."""

    @abstractmethod
    def compute(self, neg: float, gw: float, tw: float) -> float: ...


class WeightedProductRule(PriorityRule):
    """ConcreteStrategy(기본): P = (neg × 10) × gw × tw."""

    def compute(self, neg: float, gw: float, tw: float) -> float:
        return neg * 10 * gw * tw


class WeightedSumRule(PriorityRule):
    """ConcreteStrategy(대안): 부정 강도 중심 가중합. 최댓값을 곱셈식과 같은 30으로 맞춘다."""

    def compute(self, neg: float, gw: float, tw: float) -> float:
        return neg * 20 + (gw / 1.5) * 5 * (neg > 0) + (tw - 1.0) * 5 * (neg > 0)


class PriorityCalculator:
    def __init__(self, grade_weights: dict[str, float], urgent_threshold: float = URGENT_THRESHOLD,
                 rule: PriorityRule | None = None):
        self.grade_weights = grade_weights
        self.urgent_threshold = urgent_threshold
        self.rule = rule or WeightedProductRule()

    def grade_weight(self, grade: str | None) -> float:
        if not grade:
            return DEFAULT_GRADE_WEIGHT
        return float(self.grade_weights.get(grade, DEFAULT_GRADE_WEIGHT))

    @staticmethod
    def time_weight(hours: float) -> float:
        return 1.0 + min(max(hours, 0.0), MAX_HOURS) / MAX_HOURS

    def calculate(self, neg: float, grade: str | None, hours: float) -> PriorityScore:
        neg = min(max(neg, 0.0), 1.0)
        gw = self.grade_weight(grade)
        tw = self.time_weight(hours)
        score = round(self.rule.compute(neg, gw, tw), 2)
        return PriorityScore(
            score=score,
            neg_intensity=round(neg, 2),
            grade_weight=gw,
            time_weight=round(tw, 2),
            is_urgent=score >= self.urgent_threshold,
        )
