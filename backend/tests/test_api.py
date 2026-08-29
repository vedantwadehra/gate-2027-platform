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
