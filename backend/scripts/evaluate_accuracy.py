"""정답 표본(NFR-01) 라벨링 보조와 정확도 측정. 사용법은 data/eval/labeling-guide.md 참고.

backend 폴더에서 실행한다.
  python -m scripts.evaluate_accuracy --make-sheets ../data/eval/gold_v1.csv
  python -m scripts.evaluate_accuracy --merge-sheets ../data/eval/label_a.csv ../data/eval/label_b.csv \
      --gold ../data/eval/gold_v1.csv
  python -m scripts.evaluate_accuracy --gold ../data/eval/gold_v1.csv --agreement-only
  python -m scripts.evaluate_accuracy --gold ../data/eval/gold_v1.csv [--engine rule|llm|both]
"""
import argparse
import csv
import logging
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.business.analyzers.llm_analyzer import LLMSentimentAnalyzer
from app.business.analyzers.rule_based_analyzer import RuleBasedSentimentAnalyzer
from app.business.analyzers.topic_classifier import OTHER, TopicClassifier
from app.business.pipeline.base import FeedbackContext
from app.business.pipeline.filters import CleansingFilter
from app.infra.ai_client import AIClientError, ExternalLLMAdapter
from app.infra.config import get_settings
from app.persistence.models import Feedback, SentimentLabel

TARGET_LABEL, TARGET_TOPIC, TARGET_KAPPA, MIN_ROWS = 0.80, 0.70, 0.60, 30
TOPICS = ("품질", "배송", "가격", "서비스", OTHER)
SHEET_COLUMNS = ["id", "content", "label", "intensity", "topics"]
# 비용 추정용 Claude Haiku 5.5 요금 ($ / 100만 토큰), 환율은 근사값
PRICE_IN, PRICE_OUT, KRW = 0.10, 0.50, 1400


# ---------- 입출력 ----------
def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), [{k: (v or "").strip() for k, v in row.items()} for row in reader]


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def split_topics(text: str) -> list[str]:
    return [t.strip() for t in re.split(r"[;,/]", text) if t.strip()]


def check_labels(rows: list[dict[str, str]], suffix: str) -> list[str]:
    """라벨 칸의 값 오류를 찾아 메시지로 돌려준다."""
    problems = []
    for r in rows:
        label = r.get(f"label{suffix}", "")
        if label not in SentimentLabel.ALL:
            problems.append(f"{r['id']}: label{suffix} '{label}' (가능: {', '.join(SentimentLabel.ALL)})")
        bad = [t for t in split_topics(r.get(f"topics{suffix}", "")) if t not in TOPICS]
        if bad or not split_topics(r.get(f"topics{suffix}", "")):
            problems.append(f"{r['id']}: topics{suffix} '{r.get(f'topics{suffix}', '')}' (가능: {', '.join(TOPICS)})")
        inten = r.get(f"intensity{suffix}", "")
        if inten:
            try:
                if not 0.0 <= float(inten) <= 1.0:
                    raise ValueError(inten)
            except ValueError:
                problems.append(f"{r['id']}: intensity{suffix} '{inten}' (0~1 숫자)")
    return problems


# ---------- 라벨링 시트 ----------
def make_sheets(gold_path: Path) -> None:
    """상대 라벨이 보이지 않도록 사람별 빈 라벨링 시트를 만든다."""
    _, rows = read_csv(gold_path)
    empty = [r["id"] for r in rows if not r.get("content")]
    if empty:
        sys.exit(f"content 가 비어 있는 행이 있습니다: {', '.join(empty)} — 문장 작성을 먼저 끝내세요.")
    for who in ("a", "b"):
        out = gold_path.parent / f"label_{who}.csv"
        write_csv(out, SHEET_COLUMNS, [{"id": r["id"], "content": r["content"]} for r in rows])
        print(f"만들었습니다: {out}  ({'김한서' if who == 'a' else '민준형'}용, label·intensity·topics 칸만 채우세요)")


def merge_sheets(sheet_a: Path, sheet_b: Path, gold_path: Path) -> None:
    """두 사람의 시트를 gold 파일의 *_a / *_b 칸에 넣고, 일치한 값은 gold_* 에도 채운다."""
    columns, gold = read_csv(gold_path)
    by_a = {r["id"]: r for r in read_csv(sheet_a)[1]}
    by_b = {r["id"]: r for r in read_csv(sheet_b)[1]}
    for r in gold:
        a, b = by_a.get(r["id"], {}), by_b.get(r["id"], {})
        for suffix, src in (("a", a), ("b", b)):
            r[f"label_{suffix}"], r[f"intensity_{suffix}"], r[f"topics_{suffix}"] = (
                src.get("label", "").upper(), src.get("intensity", ""), src.get("topics", ""))
    problems = check_labels(gold, "_a") + check_labels(gold, "_b")
    if problems:
        print("라벨 칸을 고친 뒤 다시 합치세요:\n  " + "\n  ".join(problems))
        sys.exit(1)
    disagree = []
    for r in gold:
        same_label = r["label_a"] == r["label_b"]
        if same_label:
            r["gold_label"] = r["label_a"]
            if r["intensity_a"] == r["intensity_b"]:
                r["gold_intensity"] = r["intensity_a"]
        if split_topics(r["topics_a"]) == split_topics(r["topics_b"]):
            r["gold_topics"] = r["topics_a"]
        need_intensity = r["label_a"] == SentimentLabel.NEGATIVE and not r["gold_intensity"]
        if not same_label or not r["gold_topics"] or need_intensity:
            disagree.append(r["id"])
    write_csv(gold_path, columns, gold)
    print(f"합쳤습니다: {gold_path}")
    print(f"협의가 필요한 행(감정·주제·부정 강도 불일치) {len(disagree)}건: {', '.join(disagree) or '없음'}")
    print("→ gold_label / gold_intensity / gold_topics 칸을 직접 채우고 note 에 한 줄 남기세요.")


# ---------- 계산 ----------
def cohen_kappa(a: list[str], b: list[str]) -> float:
    n = len(a)
    po = sum(x == y for x, y in zip(a, b, strict=True)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(a) | set(b)) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def agreement(rows: list[dict[str, str]]) -> str:
    problems = check_labels(rows, "_a") + check_labels(rows, "_b")
    if problems:
        sys.exit("라벨 칸을 먼저 채우세요:\n  " + "\n  ".join(problems[:20]))
    a, b = [r["label_a"] for r in rows], [r["label_b"] for r in rows]
    same = sum(x == y for x, y in zip(a, b, strict=True))
    top_same = sum(split_topics(r["topics_a"])[0] == split_topics(r["topics_b"])[0] for r in rows)
    k = cohen_kappa(a, b)
    diff = [r["id"] for r in rows if r["label_a"] != r["label_b"]]
    verdict = ("기준 충족" if k >= TARGET_KAPPA
               else f"기준({TARGET_KAPPA}) 미달 → 가이드를 다시 맞추고 불일치 건을 재검토")
    return (f"감정 일치 {same}/{len(rows)} ({same / len(rows):.0%}), Cohen's kappa {k:.2f} → {verdict}\n"
            f"대표 주제 일치 {top_same}/{len(rows)}\n불일치 행: {', '.join(diff) or '없음'}")


@dataclass
class Pred:
    label: str
    intensity: float
    topics: list[str]


def score(gold: list[dict[str, str]], preds: list[Pred | None]) -> dict:
    """gold 와 예측을 비교한다. 예측이 None(AI 실패)인 행은 제외한다."""
    pairs = [(g, p) for g, p in zip(gold, preds, strict=True) if p is not None]
    n = len(pairs)
    by_type: dict[str, list[bool]] = {}
    confusion: Counter = Counter()
    topic_hit, jaccard, intens_err = 0, [], []
    for g, p in pairs:
        ok = g["gold_label"] == p.label
        by_type.setdefault(g.get("case_type", "?"), []).append(ok)
        confusion[(g["gold_label"], p.label)] += 1
        gt = split_topics(g["gold_topics"])
        topic_hit += bool(gt) and bool(p.topics) and gt[0] == p.topics[0]
        union = set(gt) | set(p.topics)
        jaccard.append(len(set(gt) & set(p.topics)) / len(union) if union else 1.0)
        if g["gold_label"] == SentimentLabel.NEGATIVE and g.get("gold_intensity"):
            pred_int = p.intensity if p.label == SentimentLabel.NEGATIVE else 0.0
            intens_err.append(abs(pred_int - float(g["gold_intensity"])))
    return {
        "n": n,
        "failed": len(preds) - n,
        "label_acc": sum(g["gold_label"] == p.label for g, p in pairs) / n if n else 0.0,
        "topic_acc": topic_hit / n if n else 0.0,
        "jaccard": sum(jaccard) / n if n else 0.0,
        "intensity_mae": sum(intens_err) / len(intens_err) if intens_err else None,
        "intensity_n": len(intens_err),
        "by_type": {k: (sum(v), len(v)) for k, v in by_type.items()},
        "confusion": confusion,
    }


# ---------- 예측 엔진 ----------
def _clean(row: dict[str, str]) -> str:
    fb = Feedback(content=row["content"], source="REVIEW")
    return CleansingFilter().process(FeedbackContext(feedback=fb)).clean_text


def predict_rule(rows: list[dict[str, str]]) -> list[Pred | None]:
    rule, topics = RuleBasedSentimentAnalyzer(), TopicClassifier()
    out: list[Pred | None] = []
    for r in rows:
        text = _clean(r)
        s = rule.analyze(text)
        out.append(Pred(s.label, float(s.intensity), list(topics.classify(text))))
    return out


def predict_llm(rows: list[dict[str, str]]) -> tuple[list[Pred | None], dict]:
    llm, topics = LLMSentimentAnalyzer(ExternalLLMAdapter()), TopicClassifier()
    usage = {"in": 0, "out": 0, "times": []}

    class Tap(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            m = re.search(r"입력 (\d+)·출력 (\d+)", record.getMessage())
            if m:
                usage["in"] += int(m[1])
                usage["out"] += int(m[2])

    log = logging.getLogger("app.infra.ai_client")
    log.setLevel(logging.INFO)
    log.addHandler(Tap())
    out: list[Pred | None] = []
    for r in rows:
        text = _clean(r)
        t0 = time.perf_counter()
        try:
            res = llm.analyze_full(text)
        except AIClientError as e:
            print(f"  [AI 실패→측정 제외] {r['id']}: {e}")
            out.append(None)
            continue
        usage["times"].append(time.perf_counter() - t0)
        scores = res.topic_scores or topics.classify(text)
        out.append(Pred(res.sentiment.label, float(res.sentiment.intensity), list(scores)))
    return out, usage


# ---------- 보고서 ----------
def pct(x: float) -> str:
    return f"{x:.1%}"


def engine_section(name: str, res: dict, extra: str = "") -> str:
    lab_ok = "충족" if res["label_acc"] >= TARGET_LABEL else "미달"
    top_ok = "충족" if res["topic_acc"] >= TARGET_TOPIC else "미달"
    lines = [
        f"## {name}", "",
        f"- 측정 {res['n']}건 (AI 실패로 제외 {res['failed']}건)",
        f"- 감정 3분류 일치율: **{pct(res['label_acc'])}** (목표 {TARGET_LABEL:.0%} → {lab_ok})",
        f"- 대표 주제 일치율: **{pct(res['topic_acc'])}** (목표 {TARGET_TOPIC:.0%} → {top_ok}), "
        f"주제 겹침(Jaccard) {res['jaccard']:.2f}",
    ]
    if res["intensity_mae"] is not None:
        lines.append(f"- 부정 강도 평균 오차: {res['intensity_mae']:.2f} ({res['intensity_n']}건, 0~1 범위)")
    if extra:
        lines.append(extra)
    lines += ["", "유형별 감정 일치:", "", "| case_type | 일치/전체 |", "|---|---|"]
    lines += [f"| {k} | {ok}/{tot} |" for k, (ok, tot) in sorted(res["by_type"].items())]
    labels = SentimentLabel.ALL
    lines += ["", "혼동 행렬 (행=정답, 열=예측):", ""]
    lines += ["| 정답＼예측 | " + " | ".join(labels) + " |", "|---|---|---|---|"]
    lines += [f"| {g} | " + " | ".join(str(res["confusion"][(g, p)]) for p in labels) + " |" for g in labels]
    return "\n".join(lines)


def misses_section(name: str, gold: list[dict[str, str]], preds: list[Pred | None]) -> str:
    """감정 또는 대표 주제가 정답과 다른 행을 표로 뽑는다 (원인 분석용: 시스템 오류/기준 모호/입력 실수)."""
    lines = [f"### {name}: 불일치 행", "",
             "| id | 유형 | 문장 | 정답 감정/주제 | 예측 감정/주제 | 어긋난 것 |", "|---|---|---|---|---|---|"]
    for g, p in zip(gold, preds, strict=True):
        if p is None:
            continue
        gt = split_topics(g["gold_topics"])
        bad = [w for w, bad_ in (("감정", g["gold_label"] != p.label),
                                 ("주제", not (gt and p.topics and gt[0] == p.topics[0]))) if bad_]
        if bad:
            lines.append(f"| {g['id']} | {g['case_type']} | {g['content'].strip()} | "
                         f"{g['gold_label']}/{';'.join(gt)} | "
                         f"{p.label}/{';'.join(p.topics[:2])} | {'·'.join(bad)} |")
    return "\n".join(lines)


def run_measure(gold_path: Path, engine: str, out: Path | None) -> None:
    _, rows = read_csv(gold_path)
    problems = check_labels([{**r, "label_x": r["gold_label"], "topics_x": r["gold_topics"],
                              "intensity_x": r["gold_intensity"]} for r in rows], "_x")
    if problems:
        names = {"label_x": "gold_label", "topics_x": "gold_topics", "intensity_x": "gold_intensity"}
        shown = [re.sub(r"(label|topics|intensity)_x", lambda m: names[m.group(0)], p) for p in problems[:20]]
        sys.exit(f"정답 칸(gold_label·gold_intensity·gold_topics)을 먼저 채우세요 "
                 f"(문제 {len(problems)}건, 20건까지 표시):\n  " + "\n  ".join(shown))
    if len(rows) < MIN_ROWS:
        print(f"주의: 표본이 {len(rows)}건입니다 (목표 {MIN_ROWS}건 이상).")
    sections = [f"# 정확도 측정 보고서 (NFR-01)\n\n- 측정 시각: {datetime.now():%Y-%m-%d %H:%M}\n"
                f"- 정답 표본: {gold_path.name} {len(rows)}건"]
    print(f"정답 표본 {len(rows)}건, 엔진: {engine}")
    if engine in ("rule", "both"):
        rule_preds = predict_rule(rows)
        sections.append(engine_section("규칙 기반 (감성 사전 + 키워드 주제)", score(rows, rule_preds)))
        sections.append(misses_section("규칙 기반", rows, rule_preds))
    if engine in ("llm", "both"):
        s = get_settings()
        if not s.ai_api_key:
            print("AI 키가 없어 AI 측정은 건너뜁니다 (.env 에 FEEDBACKCARE_AI_API_KEY 필요).")
        else:
            preds, usage = predict_llm(rows)
            t = usage["times"]
            cost = usage["in"] / 1e6 * PRICE_IN + usage["out"] / 1e6 * PRICE_OUT
            extra = (f"- 응답 시간 평균 {sum(t) / len(t):.1f}초, 최대 {max(t):.1f}초 (기준 5초)\n"
                     f"- 토큰 입력 {usage['in']} / 출력 {usage['out']} → 약 {cost * KRW:.1f}원 "
                     "(Haiku 5.5 요금 기준 추정)"
                     if t else "")
            sections.append(engine_section(f"AI ({s.ai_model}, effort {s.ai_effort})", score(rows, preds), extra))
            sections.append(misses_section("AI", rows, preds))
    report = "\n\n".join(sections) + "\n"
    print("\n" + report)
    path = out or gold_path.parent / f"report_{datetime.now():%Y%m%d_%H%M}.md"
    path.write_text(report, encoding="utf-8")
    print(f"보고서 저장: {path}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="NFR-01 정답 표본 라벨링 보조·정확도 측정")
    ap.add_argument("--gold", type=Path, help="정답 표본 CSV (gold_v1.csv)")
    ap.add_argument("--make-sheets", type=Path, metavar="GOLD", help="사람별 빈 라벨링 시트 만들기")
    ap.add_argument("--merge-sheets", nargs=2, type=Path, metavar=("A", "B"), help="두 시트를 --gold 파일에 합치기")
    ap.add_argument("--agreement-only", action="store_true", help="두 사람의 일치도(kappa)만 확인")
    ap.add_argument("--engine", choices=["rule", "llm", "both"], default="both")
    ap.add_argument("--out", type=Path, help="보고서 저장 경로 (기본: gold 파일 옆 report_날짜.md)")
    args = ap.parse_args()
    if args.make_sheets:
        make_sheets(args.make_sheets)
    elif args.merge_sheets:
        if not args.gold:
            sys.exit("--gold 로 합칠 정답 파일을 지정하세요.")
        merge_sheets(args.merge_sheets[0], args.merge_sheets[1], args.gold)
    elif args.gold and args.agreement_only:
        print(agreement(read_csv(args.gold)[1]))
    elif args.gold:
        run_measure(args.gold, args.engine, args.out)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
