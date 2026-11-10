"""키워드 기반 주제 분류기 (품질/배송/가격/서비스, 해당 없음 → 기타)."""

DEFAULT_TOPIC_KEYWORDS: dict[str, list[str]] = {
    "품질": ["품질", "불량", "파손", "고장", "마감", "재질", "내구", "냄새", "사이즈", "작동"],
    "배송": ["배송", "택배", "도착", "포장", "출고", "발송", "늦게 와", "오지 않"],
    "가격": ["가격", "비싸", "저렴", "할인", "가성비", "쿠폰", "요금", "환불"],
    "서비스": ["상담", "응대", "친절", "직원", "고객센터", "답변", "문의", "교환", "AS", "A/S"],
}
OTHER = "기타"


class TopicClassifier:
    def __init__(self, keywords: dict[str, list[str]] | None = None):
        self.keywords = keywords or DEFAULT_TOPIC_KEYWORDS

    def classify(self, text: str) -> dict[str, float]:
        """{주제: 점수(0~1)} 반환. 점수 = 해당 주제 키워드 적중 수 / 전체 적중 수."""
        hits = {t: sum(text.count(k) for k in kws) for t, kws in self.keywords.items()}
        hits = {t: n for t, n in hits.items() if n > 0}
        if not hits:
            return {OTHER: 1.0}
        total = sum(hits.values())
        return {t: round(n / total, 2) for t, n in sorted(hits.items(), key=lambda x: -x[1])}
