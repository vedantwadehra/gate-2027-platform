"""Backend API + service tests (run against a temporary SQLite DB)."""

from app.api import routes
from app.db import models
from app.db.session import SessionLocal


def test_full_mock_has_65_questions(client):
    r = client.get("/api/test/CS?mock=full")
    assert r.status_code == 200
    body = r.json()
    assert body["is_full"] is True
    assert len(body["questions"]) == 65


def test_register_submit_then_analytics(client):
    email = "ci_user_%s@test.com" % str(abs(hash("ci")) % 10**6)
    reg = client.post("/api/auth/register", json={"email": email, "password": "pw12345"})
    assert reg.status_code == 200
    token = reg.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    # Grab a small paper test and submit empty answers (all wrong -> score 0).
    t = client.get("/api/test/DA", headers=h).json()
    assert "questions" in t
    sub = client.post(
        "/api/test/submit",
        headers=h,
        json={"paper": "DA", "answers": {}},
    )
    assert sub.status_code == 200
    assert "attempt_id" in sub.json()

    an = client.get("/api/analytics", headers=h).json()
    assert an["total_attempts"] >= 1
    assert an["rank_estimate"] is not None
    assert "estimated_rank" in an["rank_estimate"]


def test_admin_rejects_bad_answer_index(client):
    # Demo account is seeded as admin.
    login = client.post(
        "/api/auth/login",
        json={"email": "demo@gatetest.com", "password": "test1234"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    bad = client.post(
        "/api/admin/questions",
        headers=h,
        json={
            "paper": "DA",
            "qid": "_ci_bad",
            "section": "da_prob_stats",
            "text": "x",
            "options": ["a", "b"],
            "answer": 9,  # out of range
        },
    )
    assert bad.status_code == 400
    # Clean up in case it was (incorrectly) created.
    client.delete("/api/admin/questions/_ci_bad?paper=DA", headers=h)


def test_admin_requires_key_or_admin_user(client):
    # No auth at all -> 403.
    assert client.get("/api/admin/questions").status_code == 403


def test_sm2_reschedules_card():
    c = models.Flashcard(user_id=1, paper="DA", front="f", back="b")
    routes._sm2(c, 4)  # Good -> first successful review
    assert c.interval == 1 and c.reps == 1
    routes._sm2(c, 4)  # Good -> second successful review
    assert c.interval == 6 and c.reps == 2
    routes._sm2(c, 0)  # Again (fail) -> reset
    assert c.reps == 0 and c.lapses == 1


def test_llm_cache_roundtrip():
    db = SessionLocal()
    try:
        key = routes._cache_key("chat", "DA", "hello-cache", "")
        routes._cache_set(db, key, "cached-value")
        assert routes._cache_get(db, key) == "cached-value"
    finally:
        db.close()


def _true_answers(qids):
    db = SessionLocal()
    try:
        rows = db.query(models.Question).filter(models.Question.qid.in_(qids)).all()
        return {r.qid: r.answer for r in rows}
    finally:
        db.close()


def test_paper_sets_listed(client):
    for paper in ("DA", "CS"):
        r = client.get(f"/api/test/{paper}/papers")
        assert r.status_code == 200
        body = r.json()
        assert len(body["sets"]) >= 1
        assert body["sets"][0]["total_marks"] == 100
        assert body["sets"][0]["total_questions"] == 65
        assert len(body["sections"]) >= 8


def test_paper_set_gate_pattern_and_stability(client):
    a = client.get("/api/test/DA?mock=full&set=1").json()
    b = client.get("/api/test/DA?mock=full&set=1").json()
    assert len(a["questions"]) == 65
    assert a["total_marks"] == 100
    assert a["paper_set"] == 1 and a["sets_total"] >= 1
    assert [q["id"] for q in a["questions"]] == [q["id"] for q in b["questions"]]
    assert all(q["section"] == "da_aptitude" for q in a["questions"][:10])
    assert [q["marks"] for q in a["questions"][:5]] == [1] * 5
    assert [q["marks"] for q in a["questions"][5:10]] == [2] * 5
    assert [q["marks"] for q in a["questions"][10:35]] == [1] * 25
    assert [q["marks"] for q in a["questions"][35:]] == [2] * 30
    if a["sets_total"] > 1:
        c = client.get("/api/test/DA?mock=full&set=2").json()
        assert not (set(q["id"] for q in a["questions"]) & set(q["id"] for q in c["questions"]))


def test_paper_set_invalid(client):
    assert client.get("/api/test/DA?mock=full&set=9999").status_code == 400


def _full_correct(qids):
    """Type-correct perfect answers: MCQ index, MSQ index list, NAT number."""
    db = SessionLocal()
    try:
        rows = db.query(models.Question).filter(models.Question.qid.in_(qids)).all()
        out = {}
        for r in rows:
            qt = r.qtype or "MCQ"
            if qt == "MSQ":
                out[r.qid] = sorted(r.answer_list)
            elif qt == "NAT":
                out[r.qid] = r.answer_num
            else:
                out[r.qid] = r.answer
        return out
    finally:
        db.close()


def test_submit_marks_math(client):
    t = client.get("/api/test/CS?mock=full&set=1").json()
    qs = t["questions"]
    qids = [q["id"] for q in qs]
    truth = _full_correct(qids)
    assert len(truth) == 65
    marks = {q["id"]: q["marks"] for q in qs}
    qtype = {q["id"]: q.get("qtype", "MCQ") for q in qs}
    # All correct -> full marks.
    r = client.post("/api/test/submit", json={"paper": "CS", "answers": truth, "qids": qids}).json()
    assert r["correct"] == 65 and r["total"] == 65
    assert r["marks_obtained"] == 100 and r["max_marks"] == 100
    # All wrong -> MCQ -1/3 each; MSQ/NAT zero (no negative marking).
    wrong = {}
    for qid, ans in truth.items():
        if qtype[qid] == "MSQ":
            wrong[qid] = [(ans[0] + 1) % 4] if ans else [0]
        elif qtype[qid] == "NAT":
            wrong[qid] = ans + 1000
        else:
            wrong[qid] = (ans + 1) % 4
    r2 = client.post("/api/test/submit", json={"paper": "CS", "answers": wrong, "qids": qids}).json()
    expected = round(sum(-round(marks[q] / 3, 2) for q in qids if qtype[q] == "MCQ"), 2)
    assert r2["correct"] == 0 and r2["marks_obtained"] == expected
    # Skipped -> zero.
    r3 = client.post("/api/test/submit", json={"paper": "CS", "answers": {}, "qids": qids[:5]}).json()
    assert r3["total"] == 5 and r3["marks_obtained"] == 0
    assert r3["max_marks"] == sum(marks[q] for q in qids[:5])


def test_paper_set_type_mix(client):
    from collections import Counter
    for paper in ("DA", "CS"):
        body = client.get(f"/api/test/{paper}?mock=full&set=1").json()
        tc = Counter((q.get("qtype", "MCQ"), q["marks"]) for q in body["questions"])
        assert len(body["questions"]) == 65
        assert sum(q["marks"] for q in body["questions"]) == 100
        assert tc[("MSQ", 1)] == 5 and tc[("MSQ", 2)] == 9
        assert tc[("NAT", 1)] == 6 and tc[("NAT", 2)] == 10
        assert all(q["section"].endswith("aptitude") for q in body["questions"][:10])


def test_msq_nat_scoring(client):
    t = client.get("/api/test/DA?mock=full&set=1").json()
    msqs = [q for q in t["questions"] if q.get("qtype") == "MSQ"][:3]
    nats = [q for q in t["questions"] if q.get("qtype") == "NAT"][:3]
    assert msqs and nats
    db = SessionLocal()
    try:
        rows = db.query(models.Question).filter(
            models.Question.qid.in_([q["id"] for q in msqs + nats])).all()
        truth = {r.qid: r for r in rows}
    finally:
        db.close()
    qids = [q["id"] for q in msqs + nats]
    # All correct: MSQ exact sets + NAT exact values.
    answers = {}
    for q in msqs:
        answers[q["id"]] = sorted(truth[q["id"]].answer_list)
    for q in nats:
        answers[q["id"]] = truth[q["id"]].answer_num
    r = client.post("/api/test/submit", json={"paper": "DA", "answers": answers, "qids": qids}).json()
    assert r["correct"] == len(qids)
    assert r["marks_obtained"] == r["max_marks"]
    # MSQ partial (drop one option) scores zero; NAT far outside tolerance scores zero.
    partial = dict(answers)
    first_msq = msqs[0]["id"]
    partial[first_msq] = sorted(truth[first_msq].answer_list)[:-1]
    first_nat = nats[0]["id"]
    partial[first_nat] = (truth[first_nat].answer_num or 0) + 1000
    r2 = client.post("/api/test/submit", json={"paper": "DA", "answers": partial, "qids": qids}).json()
    by_id = {x["id"]: x for x in r2["results"]}
    assert by_id[first_msq]["marks"] == 0 and not by_id[first_msq]["is_correct"]
    assert by_id[first_nat]["marks"] == 0 and not by_id[first_nat]["is_correct"]


def test_topic_sets_listed(client):
    r = client.get("/api/test/CS/topics")
    assert r.status_code == 200
    topics = r.json()["topics"]
    assert len(topics) == 12
    ds = next(t for t in topics if t["id"] == "cs_ds_algo")
    assert ds["questions"] > 0 and ds["sets"] >= 1


def test_topic_set_build_and_range(client):
    a = client.get("/api/test/DA?section=da_prob_stats&topic_set=1").json()
    assert 15 <= len(a["questions"]) <= 25
    assert a["topic_set"] == 1 and a["topic_sets_total"] >= 1
    assert all(q["section"] == "da_prob_stats" for q in a["questions"])
    b = client.get("/api/test/DA?section=da_prob_stats&topic_set=1").json()
    assert [q["id"] for q in a["questions"]] == [q["id"] for q in b["questions"]]
    assert client.get("/api/test/DA?section=da_prob_stats&topic_set=9999").status_code == 400
    assert client.get("/api/test/DA?topic_set=1").status_code == 400
