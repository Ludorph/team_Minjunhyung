from app.business.analyzers.base import SentimentAnalyzer
from app.persistence.models import SentimentLabel, SentimentResult

# 간단한 한국어 감성 사전 (어간 기준, +긍정 / -부정)
DEFAULT_LEXICON: dict[str, float] = {
    # 부정
    "불친절": -0.6, "안 좋": -0.5, "별로": -0.4, "불만": -0.5, "실망": -0.6, "최악": -0.9,
    "화가": -0.7, "짜증": -0.6, "엉망": -0.7, "불량": -0.7, "파손": -0.7, "고장": -0.6,
    "환불": -0.4, "늦": -0.4, "느리": -0.4, "비싸": -0.4, "아쉽": -0.3, "오지 않": -0.5,
    "답이 없": -0.5, "다시는": -0.5,
    # 긍정
    "만족": 0.6, "감사": 0.5, "친절": 0.5, "좋": 0.5, "최고": 0.8, "추천": 0.6,
    "빠르": 0.4, "훌륭": 0.7, "저렴": 0.4, "괜찮": 0.3, "재구매": 0.5,
}


class RuleBasedSentimentAnalyzer(SentimentAnalyzer):
    """Strategy 패턴의 ConcreteStrategy: 감성 사전 기반 분석 (AI 장애 시 대체 분석기)."""

    def __init__(self, lexicon: dict[str, float] | None = None):
        self.lexicon = lexicon or DEFAULT_LEXICON
        # 긴 표현 우선 매칭 ("불친절"이 "친절"보다 먼저)
        self._terms = sorted(self.lexicon, key=len, reverse=True)

    def analyze(self, text: str) -> SentimentResult:
        rest = text
        total, hits = 0.0, 0
        for term in self._terms:
            n = rest.count(term)
            if n:
                total += self.lexicon[term] * n
                hits += n
                rest = rest.replace(term, " ")
        if total > 0.05:
            label = SentimentLabel.POSITIVE
        elif total < -0.05:
            label = SentimentLabel.NEGATIVE
        else:
            label = SentimentLabel.NEUTRAL
        intensity = 0.0 if label == SentimentLabel.NEUTRAL else min(1.0, abs(total))
        confidence = min(0.9, 0.5 + 0.1 * hits) if hits else 0.4
        return SentimentResult(label=label, intensity=round(intensity, 2),
                               confidence=round(confidence, 2), analyzer="RULE")
