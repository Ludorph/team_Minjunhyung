"""성능 측정 스크립트 (NFR-02). 임시 DB로 서버를 따로 띄워 실제 HTTP 로 측정한다.

규칙 기반 분석(AI 키 없음)으로 다음을 잰다.
  - 업로드 응답 시간 (500건 CSV, 10회 중 최댓값, 기준 1초)
  - 500건 분석 완료까지 걸린 시간 (기준 10초)
  - 1,000건 이상 적재 후 대시보드·목록 조회 시간 (10회 중 최댓값, 기준 2초)
AI 분석 시간은 건당 응답 시간(evaluate_accuracy 측정값)으로 따로 추정한다.

사용 (backend 폴더): .venv\\Scripts\\python -m scripts.measure_performance [--out 파일.md]
"""
import argparse
import csv
import io
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "data" / "sample_feedback.csv"
PORT = 8765
BASE = f"http://127.0.0.1:{PORT}"
LIMIT_UPLOAD, LIMIT_ANALYZE, LIMIT_QUERY = 1.0, 10.0, 2.0


def make_csv(n: int, offset: int = 0) -> bytes:
    """가상 피드백 n건 CSV. 샘플 20건을 돌려 쓰되 시각을 바꿔 중복을 피한다."""
    with open(SAMPLE, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=["customer_name", "grade", "source", "written_at", "content"])
    w.writeheader()
    base = datetime(2026, 11, 1)
    for i in range(n):
        r = dict(rows[i % len(rows)])
        r["written_at"] = (base + timedelta(minutes=offset + i)).strftime("%Y-%m-%d %H:%M")
        w.writerow({k: r[k] for k in w.fieldnames})
    return out.getvalue().encode("utf-8")


def start_server(tmp: Path, use_ai: bool = False) -> subprocess.Popen:
    db_url = f"sqlite:///{(tmp / 'perf.db').as_posix()}"
    env = {**os.environ, "FEEDBACKCARE_DB_URL": db_url, "FEEDBACKCARE_DEMO_DATA": "0"}
    if not use_ai:
        env["FEEDBACKCARE_AI_API_KEY"] = ""  # 키가 없으면 규칙 기반으로 측정
    cmd = [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(PORT), "--log-level", "warning"]
    p = subprocess.Popen(cmd, env=env, cwd=Path(__file__).resolve().parents[1])
    for _ in range(60):
        try:
            if httpx.get(f"{BASE}/api/health", timeout=1).status_code == 200:
                return p
        except httpx.HTTPError:
            time.sleep(0.5)
    p.kill()
    sys.exit("서버가 시작되지 않았습니다.")


def upload(c: httpx.Client, data: bytes) -> tuple[float, dict]:
    t0 = time.perf_counter()
    r = c.post("/api/feedbacks/upload", files={"file": ("perf.csv", data, "text/csv")})
    dt = time.perf_counter() - t0
    assert r.status_code == 202, r.text
    return dt, r.json()


def wait_batch(c: httpx.Client, batch: dict, t0: float) -> float:
    while True:
        s = c.get(f"/api/feedbacks/batches/{batch['batch_id']}").json()
        if s["analyzed_rows"] >= batch["saved_rows"]:
            return time.perf_counter() - t0
        if time.perf_counter() - t0 > 300:
            sys.exit("분석이 300초 안에 끝나지 않았습니다.")
        time.sleep(0.2)


def measure_ai(n: int, out: Path | None) -> None:
    """실제 AI 로 n건을 일괄 분석하는 데 걸린 시간과 AI/대체 건수를 잰다 (기준: 500건 5분)."""
    with tempfile.TemporaryDirectory(prefix="feedbackcare-perf-") as d:
        proc = start_server(Path(d), use_ai=True)
        try:
            with httpx.Client(base_url=BASE, timeout=120) as c:
                tok = c.post("/api/auth/login", json={"login_id": "agent1", "password": "agent1234"}).json()["token"]
                c.headers["Authorization"] = f"Bearer {tok}"
                t0 = time.perf_counter()
                up_s, b = upload(c, make_csv(n))
                total_s = wait_batch(c, b, t0)
                items = c.get("/api/feedbacks").json()
        finally:
            proc.kill()
            proc.wait()
    llm = sum(1 for i in items if i["sentiment"] and i["sentiment"]["analyzer"] == "LLM")
    rule = sum(1 for i in items if i["sentiment"] and i["sentiment"]["analyzer"] == "RULE")
    ok = "충족" if total_s <= 300 else "미달"
    rep = (f"# 일괄 분석 시간 (실제 AI, NFR-02)\n\n- 측정 시각: {datetime.now():%Y-%m-%d %H:%M}\n"
           f"- {n}건 업로드 응답 {up_s:.2f}초, 분석 완료까지 {total_s:.0f}초 (기준: 500건 300초 → {ok})\n"
           f"- 분석 결과: AI {llm}건, 규칙 기반 대체 {rule}건\n")
    print(rep)
    path = out or ROOT / "data" / "eval" / f"perf_ai_{datetime.now():%Y%m%d_%H%M}.md"
    path.write_text(rep, encoding="utf-8")
    print(f"보고서 저장: {path}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="NFR-02 성능 측정")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--ai", type=int, metavar="N", help="실제 AI 로 N건 분석 시간만 측정 (.env 의 키 사용, 비용 발생)")
    args = ap.parse_args()
    if args.ai:
        return measure_ai(args.ai, args.out)
    with tempfile.TemporaryDirectory(prefix="feedbackcare-perf-") as d:
        proc = start_server(Path(d))
        try:
            with httpx.Client(base_url=BASE, timeout=120) as c:
                tok = c.post("/api/auth/login", json={"login_id": "agent1", "password": "agent1234"}).json()["token"]
                c.headers["Authorization"] = f"Bearer {tok}"

                # 1) 500건 분석 완료 시간 (업로드 응답 시간 포함 기준: 업로드 시작부터 전부 분석될 때까지)
                t0 = time.perf_counter()
                _, b = upload(c, make_csv(500))
                analyze_s = wait_batch(c, b, t0)
                print(f"500건 분석 완료: {analyze_s:.1f}초")

                # 2) 업로드 응답 10회 (매번 분석이 끝난 뒤 다음 업로드)
                ups = []
                for i in range(10):
                    t1 = time.perf_counter()
                    dt, b = upload(c, make_csv(500, offset=500 * (i + 1)))
                    ups.append(dt)
                    wait_batch(c, b, t1)
                print(f"업로드 응답 10회: 최대 {max(ups):.2f}초, 평균 {sum(ups) / len(ups):.2f}초")

                total = len(c.get("/api/feedbacks").json())

                # 3) 조회 10회씩 (총 5,500건 적재 상태)
                def timed(path: str) -> list[float]:
                    out = []
                    for _ in range(10):
                        t = time.perf_counter()
                        r = c.get(path)
                        assert r.status_code == 200
                        out.append(time.perf_counter() - t)
                    return out
                dash, lst, filt = (timed("/api/dashboard/summary"), timed("/api/feedbacks"),
                                   timed("/api/feedbacks?sentiment=NEGATIVE&urgent=true"))
        finally:
            proc.kill()
            proc.wait()

    def row(name: str, vals: list[float], limit: float) -> str:
        ok = "충족" if max(vals) <= limit else "미달"
        return f"| {name} | 최대 {max(vals):.2f}초 / 평균 {sum(vals) / len(vals):.2f}초 | {limit:g}초 | {ok} |"

    rows = [
        row("업로드 응답 (500건 CSV, 10회)", ups, LIMIT_UPLOAD),
        f"| 500건 분석 완료 (규칙 기반) | {analyze_s:.1f}초 | {LIMIT_ANALYZE:g}초 | "
        f"{'충족' if analyze_s <= LIMIT_ANALYZE else '미달'} |",
        row(f"대시보드 조회 ({total}건 적재, 10회)", dash, LIMIT_QUERY),
        row(f"목록 조회 ({total}건 적재, 10회)", lst, LIMIT_QUERY),
        row("목록 조회 + 필터(부정·긴급)", filt, LIMIT_QUERY),
    ]
    rep = (f"# 성능 측정 보고서 (NFR-02)\n\n- 측정 시각: {datetime.now():%Y-%m-%d %H:%M}\n"
           "- 환경: 로컬 uvicorn 1프로세스, 임시 SQLite, 규칙 기반 분석(AI 키 없음), 가상 데이터\n\n"
           "| 항목 | 측정값 | 기준 | 판정 |\n|---|---|---|---|\n" + "\n".join(rows) + "\n")
    print("\n" + rep)
    path = args.out or ROOT / "data" / "eval" / f"perf_{datetime.now():%Y%m%d_%H%M}.md"
    path.write_text(rep, encoding="utf-8")
    print(f"보고서 저장: {path}")


if __name__ == "__main__":
    main()
