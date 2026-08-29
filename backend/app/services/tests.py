"""Mock test service: fetch questions and score attempts."""

import random

from app.data import questions as qb
from app.data import syllabus
from app.db import models
from sqlalchemy.orm import Session


def _compute_difficulties(db: Session | None, paper: str) -> dict[str, str]:
    """Bucket questions into easy/medium/hard from historical answer accuracy."""
    if db is None:
        return {}
    rows = db.query(models.TestAttempt).filter_by(paper=paper).all()
    stat: dict[str, dict[str, int]] = {}
    for r in rows:
        for q in (r.details or {}).get("questions", []):
            s = stat.setdefault(q["id"], {"c": 0, "t": 0})
            s["t"] += 1
            if q.get("is_correct"):
                s["c"] += 1
    out = {}
    for qid, s in stat.items():
        acc = s["c"] / s["t"] if s["t"] else 0.5
        out[qid] = "easy" if acc >= 0.7 else ("hard" if acc < 0.4 else "medium")
    return out


def _section_accuracy(db: Session | None, paper: str) -> dict[str, float]:
    """Per-section accuracy from attempt history (for adaptive selection)."""
    if db is None:
        return {}
    rows = db.query(models.TestAttempt).filter_by(paper=paper).all()
    acc: dict[str, dict[str, int]] = {}
    for r in rows:
        for sec, st in (r.details or {}).get("sections", {}).items():
            a = acc.setdefault(sec, {"c": 0, "t": 0})
            a["c"] += st["correct"]
            a["t"] += st["total"]
    return {s: (v["c"] / v["t"] if v["t"] else 0.5) for s, v in acc.items()}


def _build_full_mock(qs: list[dict], paper: str) -> list[dict]:
    """GATE-style full paper: 10 GA + 55 subject questions (65 total)."""
    if paper == "CS":
        ga = [q for q in qs if q["section"] == "cs_aptitude"]
        rest = [q for q in qs if q["section"] != "cs_aptitude"]
    else:
        ga, rest = [], list(qs)
    ga = ([q for q in ga if q.get("verified")] or ga)[:10]
    rest_pool = ([q for q in rest if q.get("verified")] or rest)
    random.shuffle(rest_pool)
    chosen = list(ga) + rest_pool[: 55]
    # pad if a paper has fewer than 65 questions
    if len(chosen) < 65:
        extra = [q for q in rest if q not in chosen]
        random.shuffle(extra)
        chosen += extra[: 65 - len(chosen)]
    return chosen[:65]


def get_test(
    paper: str,
    section: str | None = None,
    sections: str | None = None,
    verified_only: bool = False,
    difficulty: str | None = None,
    mock: str | None = None,
    adaptive: bool = False,
    db: Session | None = None,
) -> dict:
    qs = qb.get_questions(paper, db) if db is not None else qb.QUESTIONS.get(paper, [])
    is_full = mock == "full"
    if is_full:
        qs = _build_full_mock(qs, paper)
    else:
        if section:
            qs = [q for q in qs if q["section"] == section]
        if sections:
            wanted = {s.strip() for s in sections.split(",") if s.strip()}
            qs = [q for q in qs if q["section"] in wanted]
        if verified_only:
            qs = [q for q in qs if q.get("verified")]

    difficulties = _compute_difficulties(db, paper) if db is not None else {}
    if adaptive and db is not None:
        # Bias the set toward weak sections and harder/unknown questions.
        sec_acc = _section_accuracy(db, paper)
        weak = {s for s, a in sec_acc.items() if a < 0.6}
        d_rank = {"hard": 0, "medium": 1, "easy": 2}

        def pri(q: dict) -> tuple:
            d = difficulties.get(q["id"], "medium")
            return (0 if q["section"] in weak else 1, d_rank.get(d, 1))

        ordered = sorted(qs, key=pri)
        target = 65 if is_full else 25
        qs = ordered[:target]
    elif difficulty and difficulties:
        want = {d.strip().lower() for d in difficulty.split(",") if d.strip()}
        filtered = [q for q in qs if difficulties.get(q["id"], "medium") in want]
        if filtered:
            qs = filtered

    # Strip correct answer from what the client receives; attach difficulty.
    questions = [
        {
            "id": q["id"],
            "section": q["section"],
            "text": q["text"],
            "options": q["options"],
            "year": q.get("year"),
            "source": q.get("source"),
            "verified": q.get("verified", False),
            "difficulty": difficulties.get(q["id"], "medium"),
        }
        for q in qs
    ]
    cfg = qb.TEST_CONFIG.get(paper, {})
    section_names = {
        s["id"]: s["name"] for s in syllabus.get_sections(paper)
    }
    duration = 180 if is_full else cfg.get("duration_minutes", 30)
    title = (f"GATE {paper} Full-Length Mock" if is_full else cfg.get("title", f"{paper} Mock Test"))
    return {
        "paper": paper,
        "section": section,
        "is_full": is_full,
        "duration_minutes": duration,
        "title": title,
        "section_names": section_names,
        "questions": questions,
    }


def score_and_save(
    db: Session, paper: str, answers: dict[str, int], user_id: int | None = None
) -> dict:
    qs = qb.get_questions(paper, db)
    correct = 0
    results = []
    for q in qs:
        chosen = answers.get(q["id"])
        is_correct = chosen == q["answer"]
        correct += int(is_correct)
        results.append(
            {
                "id": q["id"],
                "chosen": chosen,
                "correct_option": q["options"][q["answer"]],
                "is_correct": is_correct,
                "explanation": q["explanation"],
            }
        )
    total = len(qs)
    score = round((correct / total) * 100, 2) if total else 0.0

    section_stats: dict[str, dict[str, int]] = {}
    for q in qs:
        st = section_stats.setdefault(q["section"], {"correct": 0, "total": 0})
        st["total"] += 1
        if answers.get(q["id"]) == q["answer"]:
            st["correct"] += 1

    attempt = models.TestAttempt(
        user_id=user_id,
        paper=paper,
        score=score,
        total=total,
        correct=correct,
        details={
            "sections": section_stats,
            "questions": [
                {"id": q["id"], "chosen": answers.get(q["id"]), "is_correct": answers.get(q["id"]) == q["answer"]}
                for q in qs
            ],
        },
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    return {
        "attempt_id": attempt.id,
        "paper": paper,
        "score": score,
        "correct": correct,
        "total": total,
        "results": results,
    }
