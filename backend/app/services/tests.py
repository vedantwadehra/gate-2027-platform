"""Mock test service: fetch questions and score attempts."""

import random

from app.data import questions as qb
from app.data import syllabus
from app.db import models
from sqlalchemy.orm import Session

APTITUDE_SECTION = {"DA": "da_aptitude", "CS": "cs_aptitude"}

# Real GATE pattern per full paper (65 Qs, 100 marks):
# Q1-5 GA MCQ 1-mark, Q6-10 GA MCQ 2-mark,
# Q11-35 subject: 14 MCQ + 5 MSQ + 6 NAT at 1 mark,
# Q36-65 subject: 11 MCQ + 9 MSQ + 10 NAT at 2 marks.
# (Type mixes match the DA 2024-2026 official subject portions; any bucket
# shortfall for a set is backfilled with same-mark MCQs.)
_GATE_QUOTAS = {
    "ga1": 5, "ga2": 5,
    "mcq1": 14, "msq1": 5, "nat1": 6,
    "mcq2": 11, "msq2": 9, "nat2": 10,
}
_SET_SEED_SALT = "gate-paper-sets-v1"


def _marks(q: dict) -> int:
    try:
        m = int(q.get("marks", 1))
    except (TypeError, ValueError):
        m = 1
    return m if m in (1, 2) else 1


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


def _verified_pool(qs: list[dict]) -> list[dict]:
    pool = [q for q in qs if q.get("verified")]
    return pool or list(qs)


def _qtype(q: dict) -> str:
    return (q.get("qtype") or "MCQ").upper()


def _split_buckets(pool: list[dict], paper: str) -> dict[str, list[dict]]:
    apt = APTITUDE_SECTION[paper]
    ga = [q for q in pool if q["section"] == apt and _qtype(q) == "MCQ"]
    subj = [q for q in pool if q["section"] != apt]
    buckets = {
        "ga1": [q for q in ga if _marks(q) == 1],
        "ga2": [q for q in ga if _marks(q) == 2],
    }
    for t in ("MCQ", "MSQ", "NAT"):
        buckets[f"{t.lower()}1"] = [q for q in subj if _qtype(q) == t and _marks(q) == 1]
        buckets[f"{t.lower()}2"] = [q for q in subj if _qtype(q) == t and _marks(q) == 2]
    return buckets


def _shuffled(seq: list[dict], rng: random.Random) -> list[dict]:
    out = list(seq)
    rng.shuffle(out)
    return out


def _interleave(qs: list[dict]) -> list[dict]:
    """Round-robin across sections so a paper covers every subject evenly."""
    by_sec: dict[str, list[dict]] = {}
    for q in qs:
        by_sec.setdefault(q["section"], []).append(q)
    out: list[dict] = []
    pending = True
    while pending:
        pending = False
        for sec in sorted(by_sec):
            if by_sec[sec]:
                out.append(by_sec[sec].pop(0))
                pending = True
    return out


def count_paper_sets(paper: str, db: Session | None = None) -> int:
    """How many complete, non-overlapping 65Q/100-mark GATE-pattern papers fit."""
    qs = qb.get_questions(paper, db) if db is not None else qb.QUESTIONS.get(paper, [])
    b = _split_buckets(_verified_pool(qs), paper)
    return min(len(b[key]) // quota for key, quota in _GATE_QUOTAS.items())


def list_paper_sets(paper: str, db: Session | None = None) -> list[dict]:
    n = count_paper_sets(paper, db)
    return [
        {
            "set": i,
            "title": f"GATE {paper} Full-Length Paper {i}",
            "total_questions": 65,
            "total_marks": 100,
            "pattern": "10 GA (5x1 + 5x2) + 55 subject (25x1 + 30x2)",
        }
        for i in range(1, n + 1)
    ]


def _roundrobin(lists: list[list[dict]]) -> list[dict]:
    out: list[dict] = []
    idx = [0] * len(lists)
    pending = True
    while pending:
        pending = False
        for i, lst in enumerate(lists):
            if idx[i] < len(lst):
                out.append(lst[idx[i]])
                idx[i] += 1
                pending = True
    return out


def build_paper_set(paper: str, set_idx: int, db: Session | None = None) -> list[dict]:
    """Deterministic Nth full paper (1-indexed): disjoint across sets, stable
    across calls. Subject 1-mark block mixes 14 MCQ / 5 MSQ / 6 NAT and the
    2-mark block 11 / 9 / 10 (shortfalls backfilled with same-mark MCQs).
    Raises ValueError if out of range."""
    qs = qb.get_questions(paper, db) if db is not None else qb.QUESTIONS.get(paper, [])
    b = _split_buckets(_verified_pool(qs), paper)
    total = count_paper_sets(paper, db)
    if set_idx < 1 or set_idx > total:
        raise ValueError(f"paper set {set_idx} out of range (1..{total})")
    rng = random.Random(f"{_SET_SEED_SALT}:{paper}")
    used: set[str] = set()

    def take(key: str, backfill_from: str | None = None) -> list[dict]:
        # Positional slicing keeps sets disjoint and stable across calls.
        pool = _shuffled(b[key], rng)
        quota = _GATE_QUOTAS[key]
        sl = [q for q in pool[(set_idx - 1) * quota: set_idx * quota]
              if q["id"] not in used]
        if backfill_from and len(sl) < quota:
            for q in _shuffled(b[backfill_from], rng):
                if len(sl) >= quota:
                    break
                if q["id"] not in used and all(q["id"] != x["id"] for x in sl):
                    sl.append(q)
        for q in sl:
            used.add(q["id"])
        return sl

    ordered = take("ga1") + take("ga2")
    s1 = _roundrobin([take("mcq1"), take("msq1", "mcq1"), take("nat1", "mcq1")])
    s2 = _roundrobin([take("mcq2"), take("msq2", "mcq2"), take("nat2", "mcq2")])
    ordered.extend(_interleave(s1))
    ordered.extend(_interleave(s2))
    return ordered


def get_test(
    paper: str,
    section: str | None = None,
    sections: str | None = None,
    verified_only: bool = False,
    difficulty: str | None = None,
    mock: str | None = None,
    adaptive: bool = False,
    db: Session | None = None,
    paper_set: int | None = None,
) -> dict:
    qs = qb.get_questions(paper, db) if db is not None else qb.QUESTIONS.get(paper, [])
    is_full = mock == "full"
    sets_total = 0
    if is_full and paper_set:
        qs = build_paper_set(paper, paper_set, db)
    elif is_full:
        qs = _build_full_mock(qs, paper)
    if is_full:
        sets_total = count_paper_sets(paper, db)
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
    # MSQ correct sets and NAT values never leave the server (scored here).
    questions = [
        {
            "id": q["id"],
            "section": q["section"],
            "text": q["text"],
            "options": q["options"],
            "marks": _marks(q),
            "qtype": _qtype(q),
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
    if is_full and paper_set:
        title = f"GATE {paper} Full-Length Paper {paper_set}"
    else:
        title = (f"GATE {paper} Full-Length Mock" if is_full else cfg.get("title", f"{paper} Mock Test"))
    return {
        "paper": paper,
        "section": section,
        "is_full": is_full,
        "paper_set": paper_set,
        "sets_total": sets_total,
        "total_marks": sum(q.get("marks", 0) for q in questions),
        "duration_minutes": duration,
        "title": title,
        "section_names": section_names,
        "questions": questions,
    }


def score_and_save(
    db: Session,
    paper: str,
    answers: dict[str, int],
    user_id: int | None = None,
    qids: list[str] | None = None,
) -> dict:
    qs = qb.get_questions(paper, db)
    if qids:
        wanted = set(qids)
        qs = [q for q in qs if q["id"] in wanted]
    correct = 0
    marks_obtained = 0.0
    max_marks = 0
    results = []
    section_stats: dict[str, dict[str, int]] = {}
    for q in qs:
        m = _marks(q)
        max_marks += m
        chosen = answers.get(q["id"])
        qt = _qtype(q)
        if qt == "MSQ":
            ok_set = set(q.get("answer_list") or [q.get("answer", 0)])
            if chosen is None or (isinstance(chosen, list) and not chosen):
                awarded, is_correct = 0.0, False
            else:
                picked = set(chosen) if isinstance(chosen, list) else {chosen}
                # GATE MSQ: full marks only for the exact correct set, else zero.
                is_correct = picked == ok_set
                awarded = float(m) if is_correct else 0.0
            correct_opt = [q["options"][i] for i in sorted(ok_set)
                           if 0 <= i < len(q["options"])]
            res_extra = {"correct_options": correct_opt, "correct_option": None}
        elif qt == "NAT":
            target = q.get("answer_num")
            tol = q.get("answer_tol", 0) or 0
            try:
                val = float(chosen) if chosen is not None and chosen != "" else None
            except (TypeError, ValueError):
                val = None
            # GATE NAT: within the official range scores; no negative marking.
            is_correct = val is not None and target is not None and abs(val - target) <= tol + 1e-9
            awarded = float(m) if is_correct else 0.0
            res_extra = {"correct_option": None,
                         "correct_value": target, "correct_tol": tol}
        else:
            if chosen is None:
                awarded, is_correct = 0.0, False
            elif chosen == q["answer"]:
                awarded, is_correct = float(m), True
            else:
                # GATE MCQ negative marking: -1/3 of the question's marks.
                awarded, is_correct = -round(m / 3, 2), False
            res_extra = {"correct_option": q["options"][q["answer"]]}
        if is_correct:
            correct += 1
        marks_obtained += awarded
        st = section_stats.setdefault(q["section"], {"correct": 0, "total": 0})
        st["total"] += 1
        st["correct"] += int(is_correct)
        results.append(
            {
                "id": q["id"],
                "qtype": qt,
                "chosen": chosen,
                "is_correct": is_correct,
                "marks": awarded,
                "max_marks": m,
                "explanation": q["explanation"],
                **res_extra,
            }
        )
    marks_obtained = round(marks_obtained, 2)
    total = len(qs)
    score = round((correct / total) * 100, 2) if total else 0.0

    attempt = models.TestAttempt(
        user_id=user_id,
        paper=paper,
        score=score,
        total=total,
        correct=correct,
        details={
            "sections": section_stats,
            "marks_obtained": marks_obtained,
            "max_marks": max_marks,
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
        "marks_obtained": marks_obtained,
        "max_marks": max_marks,
        "results": results,
    }
