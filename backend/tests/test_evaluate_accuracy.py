"""정답 표본 측정 스크립트(scripts/evaluate_accuracy)의 계산 로직 테스트. 파일·AI 호출 없이 순수 계산만 확인한다."""
import pytest

from scripts.evaluate_accuracy import Pred, check_labels, cohen_kappa, score, split_topics


def test_cohen_kappa_known_value():
    # 일치 3/4, 우연 일치 0.5 → (0.75 - 0.5) / 0.5 = 0.5
    assert cohen_kappa(["N", "N", "P", "P"], ["N", "P", "P", "P"]) == pytest.approx(0.5)
    assert cohen_kappa(["N", "P"], ["N", "P"]) == 1.0


def test_split_topics_keeps_order():
    assert split_topics("배송; 품질") == ["배송", "품질"]
    assert split_topics("") == []


def test_check_labels_reports_bad_values():
    rows = [{"id": "G01", "label_a": "BAD", "topics_a": "배송", "intensity_a": ""},
            {"id": "G02", "label_a": "NEGATIVE", "topics_a": "날씨", "intensity_a": "1.5"}]
    problems = check_labels(rows, "_a")
    assert any("G01" in p and "label_a" in p for p in problems)
    assert any("G02" in p and "topics_a" in p for p in problems)
    assert any("G02" in p and "intensity_a" in p for p in problems)


def test_score_metrics_and_failed_rows_excluded():
    gold = [
        {"case_type": "clear_negative", "gold_label": "NEGATIVE", "gold_intensity": "0.8", "gold_topics": "배송;품질"},
        {"case_type": "sarcasm", "gold_label": "NEGATIVE", "gold_intensity": "0.5", "gold_topics": "배송"},
        {"case_type": "clear_positive", "gold_label": "POSITIVE", "gold_intensity": "", "gold_topics": "품질"},
        {"case_type": "mixed", "gold_label": "NEGATIVE", "gold_intensity": "0.3", "gold_topics": "배송"},
    ]
    preds = [Pred("NEGATIVE", 0.6, ["배송"]), Pred("POSITIVE", 0.9, ["배송"]), Pred("POSITIVE", 0.7, ["품질"]), None]
    r = score(gold, preds)
    assert r["n"] == 3 and r["failed"] == 1  # AI 실패 행은 측정에서 제외
    assert r["label_acc"] == pytest.approx(2 / 3)
    assert r["topic_acc"] == pytest.approx(1.0)  # 대표 주제 3/3
    assert r["by_type"]["sarcasm"] == (0, 1)
    # 강도 오차: |0.6-0.8| = 0.2, 예측이 POSITIVE 면 0 으로 보고 |0-0.5| = 0.5 → 평균 0.35
    assert r["intensity_mae"] == pytest.approx(0.35) and r["intensity_n"] == 2
    assert r["confusion"][("NEGATIVE", "POSITIVE")] == 1
