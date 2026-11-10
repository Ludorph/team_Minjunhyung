"""우선순위 항목 태그 (Decorator 패턴).

점수 객체를 감싸 '긴급', 'VIP' 같은 태그를 동적으로 덧붙인다.
"""
from abc import ABC, abstractmethod

from app.persistence.models import PriorityScore


class PriorityItem(ABC):
    """Decorator 패턴의 Component 인터페이스."""

    @abstractmethod
    def score(self) -> float: ...

    @abstractmethod
    def tags(self) -> list[str]: ...


class BasePriorityItem(PriorityItem):
    """Decorator 패턴의 ConcreteComponent: 태그 없는 기본 점수."""

    def __init__(self, priority: PriorityScore | None):
        self._priority = priority

    def score(self) -> float:
        return float(self._priority.score) if self._priority else 0.0

    def tags(self) -> list[str]:
        return []


class TagDecorator(PriorityItem, ABC):
    """Decorator 패턴의 Decorator(추상): inner 를 감싸고 태그 하나를 추가한다."""

    tag: str = ""

    def __init__(self, inner: PriorityItem):
        self.inner = inner

    def score(self) -> float:
        return self.inner.score()

    def tags(self) -> list[str]:
        return self.inner.tags() + [self.tag]


class UrgentTagDecorator(TagDecorator):
    """Decorator 패턴의 ConcreteDecorator: 긴급 태그."""
    tag = "긴급"


class VipTagDecorator(TagDecorator):
    """Decorator 패턴의 ConcreteDecorator: VIP 태그."""
    tag = "VIP"


def decorate(priority: PriorityScore | None, grade: str | None) -> PriorityItem:
    """점수·등급에 따라 데코레이터를 조합한다."""
    item: PriorityItem = BasePriorityItem(priority)
    if priority is not None and priority.is_urgent:
        item = UrgentTagDecorator(item)
    if grade == "VIP":
        item = VipTagDecorator(item)
    return item
