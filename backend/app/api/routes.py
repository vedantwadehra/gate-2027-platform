from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
import json
import io
import hashlib
from sqlalchemy.orm import Session

from app.db.session import get_db, SessionLocal
from app.db import models
from app.db.models import _now
from app.core.llm import model_supports_vision
from app.data import syllabus
from app.data import questions as qb
from app.services import tests as test_service
from app.services import chat as chat_service
from app.services import explain as explain_service
from app.services import retrieval
from app.api.deps import get_current_user
from app.core.config import settings
from app.util import pdf as pdf_util
from fastapi import Header

api = APIRouter()


def require_admin(
    authorization: str | None = Header(None),
    x_admin_key: str | None = Header(None, alias="X-Admin-Key"),
    user: dict | None = Depends(get_current_user),
) -> bool:
    if x_admin_key and x_admin_key == settings.admin_key:
        return True
    if user is not None and user.get("is_admin"):
        return True
    raise HTTPException(403, "Admin access required (admin key or admin user)")


import hashlib


def _cache_key(*parts: str) -> str:
    return hashlib.sha256("||".join(parts).encode()).hexdigest()[:64]


def _cache_get(db: Session, key: str) -> str | None:
    row = db.query(models.ResponseCache).filter_by(key=key).first()
    return row.value if row else None


def _cache_set(db: Session, key: str, value: str) -> None:
    db.add(models.ResponseCache(key=key, value=value))
    db.commit()


# ---------- Schemas ----------
class SubmitTest(BaseModel):
    paper: str
    answers: dict[str, int]
    user_id: int | None = None


class ChatRequest(BaseModel):
    paper: str
    message: str
    session_id: str | None = None
    model: str | None = None


class GenerateRequest(BaseModel):
    paper: str
    topic: str


class SaveQuestion(BaseModel):
    paper: str
    topic: str
    question: str
    options: list[str]
    answer_index: int = -1
    explanation: str = ""
    session_id: str | None = None


class ChatResponse(BaseModel):
    reply: str


# ---------- Guides ----------
@api.get("/papers")
def list_papers():
    return [
        {"code": "DA", "title": syllabus.SYLLABUS["DA"]["title"]},
        {"code": "CS", "title": syllabus.SYLLABUS["CS"]["title"]},
    ]


@api.get("/syllabus/{paper}")
def get_syllabus(paper: str):
    if paper not in syllabus.SYLLABUS:
        raise HTTPException(404, "Unknown paper")
    return syllabus.SYLLABUS[paper]


# ---------- Mock tests ----------
@api.get("/test/{paper}")
def get_test(
    paper: str,
    section: str | None = None,
    sections: str | None = None,
    verified_only: bool = False,
    difficulty: str | None = None,
    mock: str | None = None,
    adaptive: bool = False,
    weak: bool = False,
    user: dict | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if paper not in ("DA", "CS"):
        raise HTTPException(404, "Unknown paper")
    # Weak-sections mode: build a set of the user's weakest sections and
    # filter the test to those (requires auth + prior attempts).
    if weak and user is not None:
        uid = int(user["sub"])
        rows = (
            db.query(models.TestAttempt)
            .filter(models.TestAttempt.user_id == uid, models.TestAttempt.paper == paper)
            .all()
        )
        sec_acc: dict[str, dict[str, int]] = {}
        for r in rows:
            for sec, st in (r.details or {}).get("sections", {}).items():
                agg = sec_acc.setdefault(sec, {"correct": 0, "total": 0})
                agg["correct"] += st["correct"]
                agg["total"] += st["total"]
        weak_secs = [
            sec
            for sec, v in sec_acc.items()
            if v["total"] and (v["correct"] / v["total"]) < 0.6
        ]
        if not weak_secs and sec_acc:
            # Fall back to the single weakest section.
            weak_secs = [min(sec_acc.items(), key=lambda kv: kv[1]["correct"] / kv[1]["total"])[0]]
        if weak_secs:
            sections = ",".join(weak_secs)
    return test_service.get_test(
        paper, section, sections, verified_only, difficulty, mock, adaptive, db
    )


@api.post("/test/submit")
def submit_test(
    payload: SubmitTest,
    db: Session = Depends(get_db),
    user: dict | None = Depends(get_current_user),
):
    if payload.paper not in ("DA", "CS"):
        raise HTTPException(400, "Unknown paper")
    user_id = user["sub"] if user else payload.user_id
    return test_service.score_and_save(
        db, payload.paper, payload.answers, int(user_id) if user_id else None
    )


@api.get("/test/export/{attempt_id}")
def export_attempt_pdf(
    attempt_id: int,
    user: dict | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user is None:
        raise HTTPException(401, "Not authenticated")
    attempt = db.query(models.TestAttempt).filter_by(id=attempt_id).first()
    if not attempt:
        raise HTTPException(404, "Attempt not found")
    if (
        attempt.user_id is not None
        and attempt.user_id != int(user["sub"])
        and not user.get("is_admin")
    ):
        raise HTTPException(403, "Not your attempt")
    lines: list[str] = []
    lines.append(f"Paper: GATE {attempt.paper}")
    lines.append(f"Score: {attempt.score}%  ({attempt.correct}/{attempt.total} correct)")
    lines.append(f"Date: {attempt.created_at.strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    qmap = {
        q.qid: q
        for q in db.query(models.Question).filter_by(paper=attempt.paper).all()
    }
    for i, qa in enumerate((attempt.details or {}).get("questions", []), 1):
        q = qmap.get(qa["id"])
        if not q:
            continue
        lines.append(
            f"Q{i}. {'CORRECT' if qa['is_correct'] else 'WRONG'}  ({q.section})"
        )
        lines.append("  " + q.text)
        for oi, opt in enumerate(q.options):
            mark = ">" if oi == q.answer else " "
            lines.append(f"    {mark} {chr(65 + oi)}. {opt}")
        lines.append("")
    pdf_bytes = pdf_util.make_pdf(lines, title=f"GATE {attempt.paper} Result")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="gate_{attempt.paper}_attempt_{attempt_id}.pdf"'
        },
    )


# ---------- AI explanations (cached) ----------
@api.get("/explain/{paper}/{qid}")
async def explain(paper: str, qid: str, db: Session = Depends(get_db)):
    if paper not in ("DA", "CS"):
        raise HTTPException(404, "Unknown paper")
    q = qb.get_question(paper, qid, db)
    if not q:
        raise HTTPException(404, "Question not found")
    cached = (
        db.query(models.Explanation)
        .filter_by(paper=paper, qid=qid)
        .first()
    )
    if cached:
        return {"explanation": cached.text, "cached": True, "generated": False}
    text = await explain_service.explain_question(paper, q)
    db.add(models.Explanation(paper=paper, qid=qid, text=text))
    db.commit()
    return {"explanation": text, "cached": False, "generated": True}


@api.get("/attempts")
def my_attempts(
    user: dict | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user is None:
        raise HTTPException(401, "Not authenticated")
    from app.db import models

    rows = (
        db.query(models.TestAttempt)
        .filter(models.TestAttempt.user_id == int(user["sub"]))
        .order_by(models.TestAttempt.created_at.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "paper": r.paper,
            "score": r.score,
            "correct": r.correct,
            "total": r.total,
            "created_at": r.created_at.isoformat(),
            "sections": (r.details or {}).get("sections", {}),
        }
        for r in rows
    ]


@api.get("/analytics")
def analytics(
    user: dict | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user is None:
        raise HTTPException(401, "Not authenticated")
    import math

    from app.db import models

    rows = (
        db.query(models.TestAttempt)
        .filter(models.TestAttempt.user_id == int(user["sub"]))
        .order_by(models.TestAttempt.created_at.asc())
        .all()
    )
    if not rows:
        return {
            "total_attempts": 0,
            "avg_score": 0,
            "by_paper": {},
            "sections": {},
            "strongest": None,
            "weakest": None,
            "sections_trend": {},
            "section_improvement": {},
            "question_history": [],
            "rank_estimate": None,
        }

    by_paper: dict[str, list[float]] = {}
    section_acc: dict[str, dict[str, int]] = {}
    sections_trend: dict[str, list[dict]] = {}
    section_improvement: dict[str, float] = {}
    question_history: list[dict] = []
    for r in rows:
        by_paper.setdefault(r.paper, []).append(r.score)
        for sec, st in (r.details or {}).get("sections", {}).items():
            agg = section_acc.setdefault(sec, {"correct": 0, "total": 0})
            agg["correct"] += st["correct"]
            agg["total"] += st["total"]
            acc = round((st["correct"] / st["total"]) * 100, 1) if st["total"] else 0.0
            sections_trend.setdefault(sec, []).append(
                {"date": r.created_at.isoformat(), "accuracy": acc}
            )

    sections = {
        sec: round((v["correct"] / v["total"]) * 100, 1) if v["total"] else 0.0
        for sec, v in section_acc.items()
    }

    # Per-section improvement: last trend point minus first.
    for sec, trend in sections_trend.items():
        if len(trend) >= 2:
            section_improvement[sec] = round(trend[-1]["accuracy"] - trend[0]["accuracy"], 1)
        else:
            section_improvement[sec] = 0.0

    # Question-level history (join qid -> section via the question bank).
    sec_lookup: dict[str, dict[str, str]] = {}
    for p in ("DA", "CS"):
        sec_lookup[p] = {q["id"]: q.get("section", "") for q in qb.get_questions(p, db)}
    for r in rows:
        for q in (r.details or {}).get("questions", []):
            qid = q.get("id")
            question_history.append(
                {
                    "attempt_id": r.id,
                    "date": r.created_at.isoformat(),
                    "paper": r.paper,
                    "section": sec_lookup.get(r.paper, {}).get(qid, ""),
                    "qid": qid,
                    "correct": bool(q.get("is_correct")),
                    "chosen": q.get("chosen"),
                }
            )
    question_history.reverse()  # most recent first
    question_history = question_history[:400]

    # Rank / percentile estimate from the most recent full-length mock.
    ranked = sorted(sections.items(), key=lambda kv: kv[1])
    last_full = next(
        (r for r in reversed(rows) if (r.details or {}).get("is_full")), None
    )
    ref = last_full or rows[-1]
    ref_score = ref.score
    is_full = bool((ref.details or {}).get("is_full"))
    # Heuristic GATE curve: ~50th percentile at 45%, steep tail above 60.
    percentile = 100.0 / (1.0 + math.exp(-(ref_score - 45.0) / 8.0))
    cohort = 100000
    est_rank = max(1, round(cohort * (1 - percentile / 100.0)))
    rank_estimate = {
        "score": ref_score,
        "is_full": is_full,
        "estimated_percentile": round(min(99.9, max(0.1, percentile)), 1),
        "estimated_rank": est_rank,
        "cohort_size": cohort,
        "note": (
            "Estimate based on a heuristic GATE score->rank curve; not official."
            if is_full
            else "Based on a sectional mock (not a full-length paper) — take a full mock for a better estimate."
        ),
    }

    return {
        "total_attempts": len(rows),
        "avg_score": round(sum(r.score for r in rows) / len(rows), 2),
        "by_paper": {
            p: {"avg": round(sum(s) / len(s), 2), "attempts": len(s)}
            for p, s in by_paper.items()
        },
        "sections": sections,
        "strongest": ranked[-1][0] if ranked else None,
        "weakest": ranked[0][0] if ranked else None,
        "sections_trend": sections_trend,
        "section_improvement": section_improvement,
        "question_history": question_history,
        "rank_estimate": rank_estimate,
    }


# ---------- AI tutor ----------
@api.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, db: Session = Depends(get_db)):
    if req.paper not in ("DA", "CS"):
        raise HTTPException(400, "Unknown paper")
    key = _cache_key("chat", req.paper, req.message, req.model or "")
    cached = _cache_get(db, key)
    if cached is not None:
        return ChatResponse(reply=cached)
    reply = await chat_service.answer_question(req.paper, req.message, req.model)
    _cache_set(db, key, reply)
    return ChatResponse(reply=reply)


@api.post("/chat/stream")
async def chat_stream(
    paper: str = Form(...),
    message: str = Form(""),
    session_id: str | None = Form(None),
    model: str | None = Form(None),
    image: UploadFile | None = File(None),
    user: dict | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if paper not in ("DA", "CS"):
        raise HTTPException(400, "Unknown paper")

    # --- Image handling: OCR for text-only models, multimodal for vision models ---
    image_bytes: bytes | None = None
    image_media: str | None = None
    ocr_text = ""
    if image is not None and image.filename:
        raw = await image.read()
        if raw:
            image_bytes = raw
            image_media = image.content_type or "image/png"
            try:
                ocr_text = _ocr_image(raw)
            except Exception:
                ocr_text = ""

    final_message = message or ""
    send_image = False
    if image_bytes is not None:
        if ocr_text.strip():
            final_message = (
                f"{final_message}\n\n"
                f"[Text extracted from the attached image via OCR:]\n{ocr_text.strip()}"
            ).strip()
        if model_supports_vision(settings.llm_provider, model or settings.llm_model):
            send_image = True  # true multimodal call; OCR text above is the fallback
        else:
            if not ocr_text.strip():
                raise HTTPException(
                    400,
                    "The current model is text-only and the attached image has no "
                    "extractable text. Switch to a vision-capable model (e.g., OpenAI "
                    "gpt-4o) to discuss images/diagrams.",
                )

    history = []
    if session_id:
        msgs = (
            db.query(models.ChatMessage)
            .filter(
                models.ChatMessage.session_id == session_id,
                models.ChatMessage.paper == paper,
            )
            .order_by(models.ChatMessage.created_at.asc())
            .limit(12)
            .all()
        )
        history = [{"role": m.role, "content": m.content} for m in msgs]

    # Persist the user's message.
    if session_id:
        db.add(
            models.ChatMessage(
                user_id=int(user["sub"]) if user else None,
                session_id=session_id,
                paper=paper,
                role="user",
                content=final_message,
            )
        )
        db.commit()

    full_reply = ""
    cache_key = _cache_key("chat", paper, final_message, model or "")
    if image_bytes is not None:
        cache_key += ":" + hashlib.sha256(image_bytes).hexdigest()[:16]

    async def event_gen():
        nonlocal full_reply
        from app.db.session import SessionLocal

        # Serve a cached tutor response instantly (single chunk).
        hit = _cache_get(db, cache_key)
        if hit is not None:
            full_reply = hit
            yield f"data: {json.dumps({'token': hit})}\n\n"
            yield "data: [DONE]\n\n"
            return

        try:
            async for token in chat_service.answer_question_stream(
                paper,
                final_message,
                history,
                model,
                image=image_bytes if send_image else None,
                image_media_type=image_media,
            ):
                full_reply += token
                yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception:
            # Never surface a raw provider error to the chat UI.
            full_reply = (
                "Sorry, the tutor couldn't process that right now. "
                "If you attached an image, try a vision-capable model or rephrase "
                "your question as text."
            )
            yield f"data: {json.dumps({'token': full_reply})}\n\n"
        # Persist the assistant reply now that streaming is complete.
        if session_id:
            sdb = SessionLocal()
            try:
                sdb.add(
                    models.ChatMessage(
                        user_id=int(user["sub"]) if user else None,
                        session_id=session_id,
                        paper=paper,
                        role="assistant",
                        content=full_reply,
                    )
                )
                sdb.commit()
            finally:
                sdb.close()
        _cache_set(db, cache_key, full_reply)
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@api.get("/chat/history")
def chat_history(
    paper: str,
    session_id: str | None = None,
    user: dict | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not session_id and not user:
        return []
    q = db.query(models.ChatMessage).filter(models.ChatMessage.paper == paper)
    if session_id:
        q = q.filter(models.ChatMessage.session_id == session_id)
    else:
        q = q.filter(models.ChatMessage.user_id == int(user["sub"]))
    msgs = q.order_by(models.ChatMessage.created_at.asc()).limit(50).all()
    return [{"role": m.role, "content": m.content} for m in msgs]


@api.post("/generate")
async def generate_question(req: GenerateRequest, db: Session = Depends(get_db)):
    if req.paper not in ("DA", "CS"):
        raise HTTPException(400, "Unknown paper")
    if not req.topic.strip():
        raise HTTPException(400, "Topic is required")
    key = _cache_key("gen", req.paper, req.topic, req.model or "")
    cached = _cache_get(db, key)
    if cached is not None:
        import json as _json

        return _json.loads(cached)
    q = await chat_service.generate_question(req.paper, req.topic)
    _cache_set(db, key, json.dumps(q))
    return q


@api.post("/generate/save")
async def save_generated(req: SaveQuestion, user: dict | None = Depends(get_current_user)):
    if req.paper not in ("DA", "CS"):
        raise HTTPException(400, "Unknown paper")
    gq = models.GeneratedQuestion(
        user_id=int(user["sub"]) if user else None,
        session_id=req.session_id,
        paper=req.paper,
        topic=req.topic,
        question=req.question,
        options=req.options,
        answer_index=req.answer_index,
        explanation=req.explanation,
    )
    db = SessionLocal()
    try:
        db.add(gq)
        db.commit()
        db.refresh(gq)
        return {"id": gq.id, "saved": True}
    finally:
        db.close()


@api.get("/questions/saved")
def saved_questions(
    paper: str | None = None,
    session_id: str | None = None,
    user: dict | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not session_id and not user:
        return []
    q = db.query(models.GeneratedQuestion)
    if paper:
        q = q.filter(models.GeneratedQuestion.paper == paper)
    if session_id:
        q = q.filter(models.GeneratedQuestion.session_id == session_id)
    else:
        q = q.filter(models.GeneratedQuestion.user_id == int(user["sub"]))
    rows = q.order_by(models.GeneratedQuestion.created_at.desc()).limit(100).all()
    return [
        {
            "id": r.id,
            "paper": r.paper,
            "topic": r.topic,
            "question": r.question,
            "options": r.options,
            "answer_index": r.answer_index,
            "explanation": r.explanation,
        }
        for r in rows
    ]


# ---------- Bookmark / flag questions ----------
class BookmarkReq(BaseModel):
    paper: str
    qid: str


def _require_user(user: dict | None) -> int:
    if user is None:
        raise HTTPException(401, "Not authenticated")
    return int(user["sub"])


@api.post("/bookmark")
def toggle_bookmark(
    req: BookmarkReq,
    user: dict | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    uid = _require_user(user)
    if req.paper not in ("DA", "CS"):
        raise HTTPException(400, "Unknown paper")
    existing = (
        db.query(models.Bookmark)
        .filter_by(user_id=uid, paper=req.paper, qid=req.qid)
        .first()
    )
    if existing:
        db.delete(existing)
        db.commit()
        return {"bookmarked": False}
    q = qb.get_question(req.paper, req.qid, db)
    if not q:
        raise HTTPException(404, "Question not found")
    db.add(
        models.Bookmark(
            user_id=uid,
            paper=req.paper,
            qid=req.qid,
            section=q.get("section"),
            text=q["text"],
            options=q["options"],
            answer=q["answer"],
            explanation=q.get("explanation", ""),
        )
    )
    db.commit()
    return {"bookmarked": True}


@api.get("/bookmarks")
def list_bookmarks(
    user: dict | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    uid = _require_user(user)
    rows = (
        db.query(models.Bookmark)
        .filter_by(user_id=uid)
        .order_by(models.Bookmark.created_at.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "paper": r.paper,
            "qid": r.qid,
            "section": r.section,
            "text": r.text,
            "options": r.options,
            "answer": r.answer,
            "explanation": r.explanation,
            "folder": r.folder,
            "tags": r.tags or [],
        }
        for r in rows
    ]


class BookmarkUpdateReq(BaseModel):
    folder: str | None = None
    tags: list[str] | None = None


@api.put("/bookmarks/{bm_id}")
def update_bookmark(
    bm_id: int,
    payload: BookmarkUpdateReq,
    user: dict | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    uid = _require_user(user)
    bm = db.query(models.Bookmark).filter_by(id=bm_id, user_id=uid).first()
    if not bm:
        raise HTTPException(404, "Bookmark not found")
    if payload.folder is not None:
        bm.folder = payload.folder or None
    if payload.tags is not None:
        bm.tags = [t for t in payload.tags if t]
    db.commit()
    return {"updated": True, "folder": bm.folder, "tags": bm.tags or []}


@api.get("/bookmarks/test")
def bookmarks_test(
    paper: str,
    user: dict | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Build a mock-test-shaped payload from the user's bookmarks for a paper."""
    uid = _require_user(user)
    if paper not in ("DA", "CS"):
        raise HTTPException(400, "Unknown paper")
    rows = db.query(models.Bookmark).filter_by(user_id=uid, paper=paper).all()
    questions = [
        {
            "id": b.qid,
            "section": b.section,
            "text": b.text,
            "options": b.options,
            "year": None,
            "source": "bookmark",
            "verified": False,
        }
        for b in rows
    ]
    section_names = {s["id"]: s["name"] for s in syllabus.get_sections(paper)}
    duration = max(15, len(questions) * 2)
    return {
        "paper": paper,
        "section": None,
        "is_full": False,
        "is_bookmark_test": True,
        "duration_minutes": duration,
        "title": f"Bookmarked questions practice · {paper}",
        "section_names": section_names,
        "questions": questions,
    }


@api.get("/review/wrong")
def review_wrong(
    paper: str | None = None,
    user: dict | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    uid = _require_user(user)
    attempts = db.query(models.TestAttempt).filter_by(user_id=uid).all()
    wrong: dict[str, str] = {}
    for a in attempts:
        for q in (a.details or {}).get("questions", []):
            if not q.get("is_correct"):
                wrong[q["id"]] = a.paper
    out = []
    for qid, p in wrong.items():
        q = qb.get_question(p, qid, db)
        if not q:
            continue
        out.append(
            {
                "id": q["id"],
                "paper": p,
                "section": q.get("section"),
                "text": q["text"],
                "options": q["options"],
                "answer": q["answer"],
                "explanation": q.get("explanation", ""),
            }
        )
    if paper:
        out = [x for x in out if x["paper"] == paper]
    return out


# ---------- Notes -> flashcards ----------
def _extract_pdf(data: bytes) -> str:
    try:
        import PyPDF2

        reader = PyPDF2.PdfReader(io.BytesIO(data))
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception:
        return ""


def _ocr_image(data: bytes) -> str:
    """Run tesseract OCR on image bytes; returns extracted text."""
    import os
    import subprocess
    import tempfile

    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
            tf.write(data)
            path = tf.name
        out = subprocess.run(
            ["tesseract", path, "stdout"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return out.stdout or ""
    except Exception:
        return ""
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass


@api.post("/notes/import")
async def import_notes(
    paper: str = Form(...),
    text: str = Form(""),
    files: list[UploadFile] | None = File(None),
    user: dict | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    uid = _require_user(user)
    if paper not in ("DA", "CS"):
        raise HTTPException(400, "Unknown paper")
    content = text or ""
    if files:
        for f in files:
            raw = await f.read()
            if not raw:
                continue
            name = (f.filename or "").lower()
            if name.endswith(".pdf"):
                content += "\n" + _extract_pdf(raw)
            elif name.endswith((".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".gif")):
                content += "\n" + _ocr_image(raw)
            else:
                content += "\n" + raw.decode("utf-8", "ignore")
    if not content.strip():
        raise HTTPException(400, "Provide notes text or upload a file")
    cards = await chat_service.generate_flashcards(paper, content)
    created = 0
    for c in cards:
        db.add(
            models.Flashcard(
                user_id=uid,
                paper=paper,
                front=c.get("front", ""),
                back=c.get("back", ""),
                source="notes",
            )
        )
        created += 1
    db.commit()
    return {"created": created}


@api.get("/flashcards")
def list_flashcards(
    paper: str | None = None,
    due: bool = False,
    user: dict | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    uid = _require_user(user)
    q = db.query(models.Flashcard).filter_by(user_id=uid)
    if paper:
        q = q.filter_by(paper=paper)
    if due:
        now = _now()
        q = q.filter(
            (models.Flashcard.due_at == None) | (models.Flashcard.due_at <= now)
        )
    rows = q.order_by(models.Flashcard.created_at.desc()).limit(200).all()
    return [
        {
            "id": r.id,
            "paper": r.paper,
            "front": r.front,
            "back": r.back,
            "source": r.source,
            "ease": r.ease,
            "interval": r.interval,
            "reps": r.reps,
            "lapses": r.lapses,
            "due_at": r.due_at.isoformat() if r.due_at else None,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@api.get("/flashcards/due")
def flashcards_due(
    paper: str | None = None,
    user: dict | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    uid = _require_user(user)
    now = _now()
    q = db.query(models.Flashcard).filter_by(user_id=uid)
    if paper:
        q = q.filter_by(paper=paper)
    rows = q.filter(
        (models.Flashcard.due_at == None) | (models.Flashcard.due_at <= now)
    ).order_by(models.Flashcard.created_at.asc()).limit(200).all()
    return {
        "count": len(rows),
        "due": [
            {
                "id": r.id,
                "paper": r.paper,
                "front": r.front,
                "back": r.back,
                "source": r.source,
                "ease": r.ease,
                "interval": r.interval,
                "reps": r.reps,
                "lapses": r.lapses,
                "due_at": r.due_at.isoformat() if r.due_at else None,
            }
            for r in rows
        ],
    }


def _sm2(card: "models.Flashcard", grade: int) -> None:
    """Apply the SM-2 spaced-repetition algorithm to a flashcard.

    grade is 0-5 (standard SM-2 quality). 0-2 => fail (reset reps, show again
    soon); 3-5 => pass (grow interval by ease factor).
    """
    from datetime import timedelta

    if grade < 3:
        card.reps = 0
        card.interval = 1
        card.lapses = (card.lapses or 0) + 1
    else:
        if (card.reps or 0) == 0:
            card.interval = 1
        elif (card.reps or 0) == 1:
            card.interval = 6
        else:
            card.interval = max(1, round((card.interval or 1) * (card.ease or 2.5)))
        card.reps = (card.reps or 0) + 1
    # Update ease factor (clamped to a 1.3 minimum).
    card.ease = max(1.3, (card.ease or 2.5) + (0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02)))
    card.due_at = _now() + timedelta(days=card.interval)


class FlashcardReview(BaseModel):
    grade: int  # 0-5 (Again=0/1/2, Hard=3, Good=4, Easy=5)


@api.post("/flashcards/{card_id}/review")
def review_flashcard(
    card_id: int,
    payload: FlashcardReview,
    user: dict | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    uid = _require_user(user)
    card = (
        db.query(models.Flashcard).filter_by(id=card_id, user_id=uid).first()
    )
    if not card:
        raise HTTPException(404, "Flashcard not found")
    grade = max(0, min(5, int(payload.grade)))
    _sm2(card, grade)
    db.commit()
    return {
        "id": card.id,
        "ease": card.ease,
        "interval": card.interval,
        "reps": card.reps,
        "lapses": card.lapses,
        "due_at": card.due_at.isoformat() if card.due_at else None,
    }


@api.delete("/flashcards/{card_id}")
def delete_flashcard(
    card_id: int,
    user: dict | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    uid = _require_user(user)
    card = (
        db.query(models.Flashcard)
        .filter_by(id=card_id, user_id=uid)
        .first()
    )
    if not card:
        raise HTTPException(404, "Flashcard not found")
    db.delete(card)
    db.commit()
    return {"deleted": True}


class FlashcardUpdate(BaseModel):
    front: str | None = None
    back: str | None = None


@api.put("/flashcards/{card_id}")
def update_flashcard(
    card_id: int,
    payload: FlashcardUpdate,
    user: dict | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    uid = _require_user(user)
    card = (
        db.query(models.Flashcard)
        .filter_by(id=card_id, user_id=uid)
        .first()
    )
    if not card:
        raise HTTPException(404, "Flashcard not found")
    if payload.front is not None:
        card.front = payload.front
    if payload.back is not None:
        card.back = payload.back
    db.commit()
    return {"updated": True}


# ---------- Admin: question bank CRUD + seed/reset (X-Admin-Key) ----------
class AdminQuestion(BaseModel):
    paper: str
    qid: str
    section: str
    text: str
    options: list[str]
    answer: int = 0
    explanation: str = ""
    year: int | None = None
    source: str | None = None
    verified: bool = False


@api.get("/admin/questions")
def admin_list_questions(
    paper: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(models.Question)
    if paper:
        query = query.filter_by(paper=paper)
    if q:
        query = query.filter(models.Question.text.ilike(f"%{q}%"))
    total = query.count()
    rows = (
        query.order_by(models.Question.id.desc()).limit(limit).offset(offset).all()
    )
    return {"total": total, "items": [r.to_dict() for r in rows]}


@api.post("/admin/questions")
def admin_create_question(
    payload: AdminQuestion,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    existing = (
        db.query(models.Question)
        .filter_by(paper=payload.paper, qid=payload.qid)
        .first()
    )
    if existing:
        raise HTTPException(409, "qid already exists for this paper")
    if payload.paper not in ("DA", "CS"):
        raise HTTPException(400, "Unknown paper")
    if not (0 <= payload.answer < len(payload.options)):
        raise HTTPException(400, "answer index out of range for options")
    q = models.Question(**payload.model_dump())
    q.updated_at = _now()
    db.add(q)
    db.commit()
    db.refresh(q)
    retrieval.invalidate_index(payload.paper)
    return q.to_dict()


@api.put("/admin/questions/{qid}")
def admin_update_question(
    qid: str,
    payload: AdminQuestion,
    paper: str | None = None,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(models.Question).filter_by(qid=qid)
    if paper:
        query = query.filter_by(paper=paper)
    q = query.first()
    if not q:
        raise HTTPException(404, "Question not found")
    if not (0 <= payload.answer < len(payload.options)):
        raise HTTPException(400, "answer index out of range for options")
    for field, value in payload.model_dump().items():
        setattr(q, field, value)
    q.updated_at = _now()
    db.commit()
    retrieval.invalidate_index(q.paper)
    return q.to_dict()


@api.delete("/admin/questions/{qid}")
def admin_delete_question(
    qid: str,
    paper: str | None = None,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(models.Question).filter_by(qid=qid)
    if paper:
        query = query.filter_by(paper=paper)
    q = query.first()
    if not q:
        raise HTTPException(404, "Question not found")
    db.delete(q)
    db.commit()
    retrieval.invalidate_index(q.paper)
    return {"deleted": True}


@api.post("/admin/seed")
def admin_seed(_: bool = Depends(require_admin), db: Session = Depends(get_db)):
    from app.data import questions as qb

    n = qb.seed_questions(db)
    retrieval.invalidate_index("DA")
    retrieval.invalidate_index("CS")
    return {"seeded": n, "message": "Seeded from questions.py" if n else "Already populated"}


@api.post("/admin/reset")
def admin_reset(_: bool = Depends(require_admin), db: Session = Depends(get_db)):
    from app.data import questions as qb

    db.query(models.Question).delete()
    db.commit()
    n = qb.seed_questions(db)
    retrieval.invalidate_index("DA")
    retrieval.invalidate_index("CS")
    return {"seeded": n, "message": "Question bank reset to seed"}
