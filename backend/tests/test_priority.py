import pytest

from app.business.priority.calculator import PriorityCalculator
from app.business.priority.decorators import (
    BasePriorityItem, UrgentTagDecorator, VipTagDecorator, decorate,
)

WEIGHTS = {"VIP": 1.5, "REGULAR": 1.0, "NEW": 0.8}


@pytest.fixture()
def calc():
    return PriorityCalculator(WEIGHTS)


def test_example_from_spec(calc):
    # 0.9, VIP, 24h → 9 × 1.5 × 1.333 = 18.0 → 긴급
    p = calc.calculate(0.9, "VIP", 24)
    assert p.score == pytest.approx(18.0)
    assert p.grade_weight == 1.5
    assert p.time_weight == pytest.approx(1.33)
    assert p.is_urgent is True


@pytest.mark.parametrize("grade,expected", [("VIP", 1.5), ("REGULAR", 1.0), ("NEW", 0.8),
                                            (None, 1.0), ("", 1.0), ("GOLD", 1.0)])
def test_grade_weight(calc, grade, expected):
    assert calc.grade_weight(grade) == expected


@pytest.mark.parametrize("hours,expected", [(0, 1.0), (36, 1.5), (72, 2.0), (500, 2.0), (-3, 1.0)])
def test_time_weight_range(calc, hours, expected):
    assert calc.time_weight(hours) == pytest.approx(expected)


def test_max_score_is_30(calc):
    assert calc.calculate(1.0, "VIP", 1000).score == 30.0
    assert calc.calculate(5.0, "VIP", 1000).score == 30.0  # 강도는 1로 클램프


def test_non_negative_gives_zero(calc):
    p = calc.calculate(0.0, "VIP", 72)
    assert p.score == 0 and p.is_urgent is False


def test_urgent_threshold_boundary(calc):
    assert calc.calculate(0.75, "REGULAR", 72).is_urgent is True   # 7.5 × 1 × 2 = 15.0
    assert calc.calculate(0.74, "REGULAR", 72).is_urgent is False  # 14.8


def test_decorators_tags(calc):
    urgent = calc.calculate(0.9, "VIP", 24)
    assert decorate(urgent, "VIP").tags() == ["긴급", "VIP"]
    assert decorate(calc.calculate(0.1, "VIP", 0), "VIP").tags() == ["VIP"]
    assert decorate(calc.calculate(0.1, "NEW", 0), "NEW").tags() == []
    item = VipTagDecorator(UrgentTagDecorator(BasePriorityItem(urgent)))
    assert item.score() == pytest.approx(18.0)
