"""대시보드 집계(S02) 및 분석 정확도 검증(S07)."""
from collections import defaultdict

from sqlalchemy.orm import Session

from app.persistence.models import SentimentLabel
from app.persistence.repositories import FeedbackRepository, GoldLabelRepository


class DashboardService:
    def __init__(self, db: Session):
        self.db = db
        self.feedbacks = FeedbackRepository(db)

    def summary(self) -> dict:
        by_status = {s: 0 for s in ("PENDING", "IN_PROGRESS", "DONE")}
        by_status.update(self.feedbacks.count_by_status())
        by_sentiment = {s: 0 for s in SentimentLabel.ALL}
        by_sentiment.update(self.feedbacks.count_by_sentiment())
        trend: dict[str, dict[str, int]] = defaultdict(lambda: {s: 0 for s in SentimentLabel.ALL})
        for day, label, n in self.feedbacks.daily_sentiment():
            trend[str(day)][label] = n
        return {
            "total": sum(by_status.values()),
            "by_status": by_status,
            "by_sentiment": by_sentiment,
            "by_topic": self.feedbacks.count_by_topic(),
            "urgent_count": self.feedbacks.count_urgent_open(),
            "daily_trend": [{"date": d, **counts} for d, counts in sorted(trend.items())],
        }

    def accuracy(self) -> dict:
        """정답 라벨 표본 vs AI(또는 대체 분석기) 결과 일치율."""
        rows = []
        for g in GoldLabelRepository(self.db).all_with_feedback():
            fb = g.feedback
            predicted = fb.sentiment.label if fb.sentiment else None
            topics = fb.topic_names
            rows.append({
                "feedback_id": fb.id, "content": fb.content,
                "gold_label": g.label, "predicted_label": predicted,
                "gold_topic": g.topic, "predicted_topics": topics,
                "label_match": predicted == g.label, "topic_match": g.topic in topics,
            })
        n = len(rows)
        return {
            "sample_size": n,
            "sentiment_accuracy": round(sum(r["label_match"] for r in rows) / n, 3) if n else None,
            "topic_accuracy": round(sum(r["topic_match"] for r in rows) / n, 3) if n else None,
            "items": rows,
        }
