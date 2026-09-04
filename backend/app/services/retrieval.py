"""Vector retrieval over syllabus + questions (TF-IDF + cosine, no external deps).

This is a lightweight, dependency-free stand-in for a full vector DB (pgvector /
FAISS). It builds term-frequency inverse-document-frequency vectors for each
chunk and returns the top-k most similar to the query.
"""

import math
import re
from collections import Counter

from app.data import syllabus
from app.data import questions as qb

_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _build_chunks(paper: str) -> list[dict]:
    chunks = []
    for sec in syllabus.get_sections(paper):
        body = (
            f"Section: {sec['name']}\nGuide: {sec['guide']}\n"
            f"Study notes: {sec.get('notes', '')}\nTopics:\n"
            + "\n".join(f"- {t}" for t in sec["topics"])
        )
        chunks.append({"paper": paper, "section": sec["name"], "text": body})
    # Prefer the DB-backed bank (reflects admin edits); fall back to seed.
    try:
        from app.db.session import SessionLocal
        from app.db import models

        db = SessionLocal()
        try:
            qs = db.query(models.Question).filter_by(paper=paper).all()
        finally:
            db.close()
        qlist = [q.to_dict() for q in qs]
    except Exception:
        qlist = qb.QUESTIONS.get(paper, [])
    for q in qlist:
        qt = (q.get("qtype") or "MCQ").upper()
        opts = q.get("options") or []
        if qt == "MSQ":
            idxs = q.get("answer_list") or [q.get("answer", 0)]
            ans = ", ".join(
                opts[i] for i in idxs if isinstance(i, int) and 0 <= i < len(opts)
            )
        elif qt == "NAT":
            ans = str(q.get("answer_num"))
        else:
            ai = q.get("answer", 0)
            ans = opts[ai] if isinstance(ai, int) and 0 <= ai < len(opts) else ""
        body = (
            f"Practice question ({q['section']}): {q['text']}\n"
            f"Options: {opts}\n"
            f"Answer: {ans}\n"
            f"Explanation: {q['explanation']}"
        )
        chunks.append({"paper": paper, "section": q["section"], "text": body})
    return chunks


def invalidate_index(paper: str) -> None:
    """Drop the cached retrieval index so edits show up on next query."""
    _INDEXES.pop(paper, None)


class _Index:
    """Sparse TF-IDF with an inverted index: same cosine ranking as the old
    dense numpy version at a fraction of the memory (~MBs, not ~100MB)."""

    def __init__(self, chunks: list[dict]):
        self.chunks = chunks
        docs = [_tokenize(c["text"]) for c in chunks]
        df = Counter()
        for tokens in docs:
            for term in set(tokens):
                df[term] += 1
        n = len(docs)
        self.idf = {t: math.log((n + 1) / (c + 1)) + 1 for t, c in df.items()}
        self.norms: list[float] = []
        self.postings: dict[str, list[tuple[int, float]]] = {}
        for i, tokens in enumerate(docs):
            tf = Counter(tokens)
            norm_sq = 0.0
            for term, cnt in tf.items():
                w = (1 + math.log(cnt)) * self.idf[term]
                norm_sq += w * w
                self.postings.setdefault(term, []).append((i, w))
            self.norms.append(math.sqrt(norm_sq) or 1.0)

    def topk(self, tokens: list[str], k: int) -> list[str]:
        tf = Counter(tokens)
        qvec = {}
        for term, cnt in tf.items():
            if term in self.idf:
                qvec[term] = (1 + math.log(cnt)) * self.idf[term]
        qnorm = math.sqrt(sum(w * w for w in qvec.values()))
        if qnorm == 0 or not self.chunks:
            return []
        scores: dict[int, float] = {}
        for term, qw in qvec.items():
            for i, dw in self.postings.get(term, ()):
                scores[i] = scores.get(i, 0.0) + qw * dw
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1] / self.norms[kv[0]], kv[0]))
        return [self.chunks[i]["text"] for i, _ in ranked[:k] if scores[i] > 0]


_INDEXES: dict[str, _Index] = {}
_INDEX_TIMES: dict[str, float] = {}
_INDEX_TTL_SECONDS = 300  # rebuild at most every 5 min even without explicit invalidation


def _get_index(paper: str) -> _Index:
    import time

    stale = (
        paper not in _INDEXES
        or (time.time() - _INDEX_TIMES.get(paper, 0)) > _INDEX_TTL_SECONDS
    )
    if stale:
        _INDEXES[paper] = _Index(_build_chunks(paper))
        _INDEX_TIMES[paper] = time.time()
    return _INDEXES[paper]


def retrieve(paper: str, query: str, k: int = 4) -> list[str]:
    index = _get_index(paper)
    if not index.chunks:
        return []
    return index.topk(_tokenize(query), k)
