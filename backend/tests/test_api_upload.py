from tests.conftest import DATA_DIR

HEADER = "customer_name,grade,source,written_at,content\n"


def _upload(client, headers, name, content: bytes):
    return client.post("/api/feedbacks/upload", headers=headers,
                       files={"file": (name, content, "text/csv")})


def test_requires_login(client):
    r = _upload(client, {}, "a.csv", HEADER.encode())
    assert r.status_code == 401


def test_upload_sample_csv_and_background_analysis(client, agent_headers):
    raw = (DATA_DIR / "sample_feedback.csv").read_bytes()
    r = _upload(client, agent_headers, "sample_feedback.csv", raw)
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["total_rows"] == 20 and body["error_rows"] == 0 and body["saved_rows"] == 20

    # TestClient 는 응답 후 BackgroundTasks 까지 실행하므로 분석이 끝나 있어야 한다
    st = client.get(f"/api/feedbacks/batches/{body['batch_id']}", headers=agent_headers).json()
    assert st["analyzed_rows"] == 20

    items = client.get("/api/feedbacks", headers=agent_headers).json()
    batch_items = [i for i in items if i["batch_id"] == body["batch_id"]]
    assert len(batch_items) == 20
    assert all(i["sentiment"]["analyzer"] == "RULE" for i in batch_items)
    scores = [i["priority"]["score"] for i in items if i["priority"]]
    assert scores == sorted(scores, reverse=True)  # 우선순위 정렬
    assert any("긴급" in i["tags"] for i in batch_items)

    dash = client.get("/api/dashboard/summary", headers=agent_headers).json()
    assert dash["by_status"]["PENDING"] >= 20
    assert sum(dash["by_sentiment"].values()) >= 20
    assert {"품질", "배송", "가격", "서비스"} <= set(dash["by_topic"])
    assert dash["urgent_count"] >= 1 and dash["daily_trend"]


def test_upload_bad_rows_counted(client, agent_headers):
    csv = (HEADER
           + "홍길동,VIP,REVIEW,2026-11-01 10:00,배송이 늦어요\n"
           + "김오류,GOLD,REVIEW,2026-11-01 10:00,등급 오류\n"
           + "이오류,NEW,FAX,2026-11-01 10:00,출처 오류\n"
           + "박오류,NEW,EMAIL,어제,날짜 오류\n"
           + "최오류,NEW,EMAIL,2026-11-01,\n").encode("utf-8")
    r = _upload(client, agent_headers, "mixed.csv", csv)
    assert r.status_code == 202
    body = r.json()
    assert (body["total_rows"], body["error_rows"], body["saved_rows"]) == (5, 4, 1)
    assert [e["row"] for e in body["errors"]] == [3, 4, 5, 6]


def test_upload_bad_format_returns_400(client, agent_headers):
    r = _upload(client, agent_headers, "wrong.csv", "name,text\n홍길동,안녕\n".encode())
    assert r.status_code == 400 and "필수 컬럼 누락" in r.json()["detail"]
    r = _upload(client, agent_headers, "data.txt", HEADER.encode())
    assert r.status_code == 400
    r = _upload(client, agent_headers, "empty.csv", b"")
    assert r.status_code == 400


def test_draft_confirm_and_status_flow(client, agent_headers):
    r = client.post("/api/feedbacks", headers=agent_headers, json={
        "content": "상품이 불량이라 너무 실망했습니다", "source": "EMAIL",
        "customer_name": "단건고객", "grade": "REGULAR"})
    assert r.status_code == 201
    fid = r.json()["id"]

    def status(action):
        return client.patch(f"/api/feedbacks/{fid}/status", headers=agent_headers, json={"action": action})

    assert status("complete").status_code == 409          # 미처리 → 완료 불가
    assert status("start").status_code == 200
    assert status("complete").status_code == 409          # 확정 초안 없음

    d = client.post(f"/api/feedbacks/{fid}/drafts", headers=agent_headers, json={}).json()
    assert d["strategy"] == "APOLOGY" and "사과" in d["draft_content"]
    assert d["is_ai_generated"] is False and d["is_edited"] is False   # API 키 없음 → 템플릿 대체
    c = client.patch(f"/api/drafts/{d['id']}/confirm", headers=agent_headers,
                     json={"final_content": "수정한 최종 답변"}).json()
    assert c["confirmed"] and c["final_content"] == "수정한 최종 답변"
    assert c["is_edited"] is True

    done = status("complete")
    assert done.status_code == 200 and done.json()["status"] == "DONE"
    assert status("reopen").json()["status"] == "IN_PROGRESS"
    hist = client.get(f"/api/feedbacks/{fid}", headers=agent_headers).json()["histories"]
    assert [(h["from_status"], h["to_status"]) for h in hist] == [
        ("PENDING", "IN_PROGRESS"), ("IN_PROGRESS", "DONE"), ("DONE", "IN_PROGRESS")]


def test_accuracy_admin_only(client, agent_headers, admin_headers):
    assert client.get("/api/dashboard/accuracy", headers=agent_headers).status_code == 403
    fid = client.get("/api/feedbacks", headers=admin_headers).json()[0]["id"]
    r = client.put(f"/api/feedbacks/{fid}/gold-label", headers=admin_headers,
                   json={"label": "NEGATIVE", "topic": "배송"})
    assert r.status_code == 204
    rep = client.get("/api/dashboard/accuracy", headers=admin_headers).json()
    assert rep["sample_size"] >= 1 and rep["sentiment_accuracy"] is not None
